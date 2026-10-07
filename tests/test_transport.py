import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tests.test_storage import event


def test_receiver_commit_precedes_ack(notification_db):
    from notification_intake.main import receive_message
    from notification_store import Delivery

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
    from discord_delivery.delivery import deliver_one
    from notification_store import Delivery, accept

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
