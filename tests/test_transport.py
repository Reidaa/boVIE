import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from tests.test_storage import event


def test_receiver_commit_precedes_ack(discord_db):
    from discord_intake.main import receive_message
    from discord_store import Delivery

    discovered = event()

    class Message:
        subject = "offers.business_france.v1"
        data = discovered.model_dump_json().encode()
        acked = 0

        async def ack_sync(self, **kwargs):
            with discord_db.connect() as conn:
                assert conn.scalar(select(Delivery.event_id)) == str(
                    discovered.event_id
                )
            self.acked += 1

    message = Message()
    asyncio.run(receive_message(discord_db, message))
    asyncio.run(receive_message(discord_db, message))
    assert message.acked == 2


def test_discord_outage_then_success(discord_db):
    from discord_sender.delivery import deliver_one
    from discord_store import Delivery, accept

    discovered = event()
    accept(discord_db, discovered)
    statuses = iter([503, 204])
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(next(statuses))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            deliver_one(discord_db, client, "https://discord.invalid/webhook")
        with Session(discord_db) as session, session.begin():
            row = session.get(Delivery, str(discovered.event_id))
            assert row is not None and row.completed_at is None
            session.execute(
                update(Delivery).values(
                    available_at=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
        assert deliver_one(discord_db, client, "https://discord.invalid/webhook")
        assert not deliver_one(discord_db, client, "https://discord.invalid/webhook")
    assert len(requests) == 2


@pytest.mark.parametrize(
    ("deliveries", "delay"), [(1, 30), (2, 60), (5, 480), (8, 3600), (50, 3600)]
)
def test_failed_messages_back_off_up_to_an_hour(deliveries, delay):
    from discord_intake.main import retry_delay

    assert retry_delay(deliveries) == delay


def test_failed_message_is_retained_with_backoff():
    from discord_intake.main import handle

    class Message:
        subject = "offers.wttj.v1"
        data = b'{"version": 1}'
        metadata = SimpleNamespace(num_delivered=3, sequence=SimpleNamespace(stream=42))

        def __init__(self):
            self.delays = []

        async def nak(self, delay=None):
            self.delays.append(delay)

    message = Message()
    # An invalid event never reaches the database, so no engine is needed.
    assert asyncio.run(handle(Mock(spec=Engine), message)) is False
    assert message.delays == [120]


def test_delivery_waits_for_discord_to_save_the_message(discord_db):
    # Without wait=true, Discord can answer 204 for a message it did not save.
    from discord_sender.delivery import deliver_one
    from discord_store import accept

    accept(discord_db, event())
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "1"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert deliver_one(discord_db, client, "https://discord.invalid/webhook")
    assert requests[0].url.params["wait"] == "true"


def test_lost_lease_after_sending_is_logged(discord_db, monkeypatch):
    # Another worker owns the delivery now, so Discord may get the message twice.
    from discord_sender import delivery
    from discord_store import accept
    from loguru import logger

    accept(discord_db, event())
    monkeypatch.setattr(delivery, "finish", lambda *args: False)
    messages = []
    sink = logger.add(messages.append, level="WARNING")
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ) as client:
            assert delivery.deliver_one(
                discord_db, client, "https://discord.invalid/webhook"
            )
    finally:
        logger.remove(sink)
    assert any("lease" in message for message in messages)


def test_rate_limited_delivery_waits_for_discord(discord_db, monkeypatch):
    # Discord answers 429 with Retry-After; sending sooner only extends the limit.
    from discord_sender import delivery
    from discord_store import Delivery, accept
    from loguru import logger

    discovered = event()
    accept(discord_db, discovered)
    waits = []
    monkeypatch.setattr(delivery.time, "sleep", waits.append)
    messages = []
    sink = logger.add(messages.append, level="WARNING")
    try:
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(429, headers={"Retry-After": "7"})
            )
        ) as client:
            assert delivery.deliver_one(
                discord_db, client, "https://discord.invalid/webhook"
            )
    finally:
        logger.remove(sink)
    assert waits == [7.0]
    assert any("429" in message for message in messages)
    with Session(discord_db) as session:
        row = session.get(Delivery, str(discovered.event_id))
        assert row is not None and row.completed_at is None
        assert row.available_at >= datetime.now(UTC) + timedelta(seconds=5)


@pytest.mark.parametrize("status", [400, 302])
def test_rejected_delivery_logs_the_status_without_the_webhook(discord_db, status):
    # Exception messages contain the webhook URL, so failures log only the status.
    from discord_sender.delivery import deliver_one
    from discord_store import accept
    from loguru import logger

    accept(discord_db, event())
    messages = []
    sink = logger.add(messages.append, level="WARNING")
    try:
        with (
            httpx.Client(
                transport=httpx.MockTransport(lambda request: httpx.Response(status))
            ) as client,
            pytest.raises(httpx.HTTPStatusError),
        ):
            deliver_one(discord_db, client, "https://discord.invalid/webhook")
    finally:
        logger.remove(sink)
    assert any(f"HTTP {status}" in message for message in messages)
    assert not any("discord.invalid" in message for message in messages)
