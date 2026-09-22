import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tests.test_storage import event


def test_relay_lost_ack_retries_same_event(source_db):
    from bovie.collector import Outbox, record_page
    from bovie.transport import relay_one

    discovered = event()
    record_page(source_db, [discovered], "scan", 1)
    published = []

    class Broker:
        async def publish(self, subject, payload, **kwargs):
            published.append((subject, payload, kwargs))
            if len(published) == 1:
                raise TimeoutError("Lost publish acknowledgment")

    broker = Broker()
    with pytest.raises(TimeoutError):
        asyncio.run(relay_one(source_db, broker, "business_france"))
    with Session(source_db) as session, session.begin():
        row = session.get(Outbox, str(discovered.event_id))
        assert row is not None and row.completed_at is None
        session.execute(
            update(Outbox).values(available_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert asyncio.run(relay_one(source_db, broker, "business_france"))
    assert published[0] == published[1]


def test_receiver_commit_precedes_ack(notification_db):
    from bovie.notifications import Delivery
    from bovie.transport import receive_message

    discovered = event()

    class Message:
        subject = "offers.business_france.v1"
        data = discovered.model_dump_json().encode()
        acked = 0

        async def ack_sync(self, **kwargs):
            with notification_db.connect() as conn:
                assert conn.scalar(select(Delivery.event_id)) == str(
                    discovered.event_id
                )
            self.acked += 1

    message = Message()
    asyncio.run(receive_message(notification_db, message))
    asyncio.run(receive_message(notification_db, message))
    assert message.acked == 2


def test_discord_outage_then_success(notification_db):
    from bovie.notifications import Delivery, accept, deliver_one

    discovered = event()
    accept(notification_db, discovered)
    statuses = iter([503, 204])
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(next(statuses))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            deliver_one(notification_db, client, "https://discord.invalid/webhook")
        with Session(notification_db) as session, session.begin():
            row = session.get(Delivery, str(discovered.event_id))
            assert row is not None and row.completed_at is None
            session.execute(
                update(Delivery).values(
                    available_at=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
        assert deliver_one(notification_db, client, "https://discord.invalid/webhook")
        assert not deliver_one(
            notification_db, client, "https://discord.invalid/webhook"
        )
    assert len(requests) == 2
