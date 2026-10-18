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
        delays = []

        async def nak(self, delay=None):
            self.delays.append(delay)

    message = Message()
    # An invalid event never reaches the database, so no engine is needed.
    assert asyncio.run(handle(Mock(spec=Engine), message)) is False
    assert message.delays == [120]
