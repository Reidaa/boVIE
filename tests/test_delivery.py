from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from tests.test_storage import event


def test_duplicate_ingestion_creates_one_pending_delivery(notification_db):
    from bovie.notifications import Delivery, Inbox, accept

    discovered = event()
    assert accept(notification_db, discovered)
    assert not accept(notification_db, discovered)
    with notification_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 1
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 1


def test_reused_event_id_with_different_content_is_rejected(notification_db):
    from bovie.notifications import accept

    discovered = event()
    accept(notification_db, discovered)
    with pytest.raises(ValueError, match="payload"):
        accept(
            notification_db, discovered.model_copy(update={"source_offer_id": "other"})
        )


def test_lease_expiry_and_stale_completion(source_db):
    from bovie.collector import Outbox, record_page
    from bovie.queue import claim, finish

    record_page(source_db, [event()], "scan", 1)
    now = datetime.now(UTC) + timedelta(seconds=1)
    first = claim(source_db, Outbox, now=now, lease_seconds=10)
    assert first is not None
    assert claim(source_db, Outbox, now=now) is None
    later = now + timedelta(seconds=11)
    second = claim(source_db, Outbox, now=later)
    assert second is not None
    assert first.token != second.token
    assert not finish(source_db, Outbox, first, now=later)
    assert finish(source_db, Outbox, second, now=later)
    assert claim(source_db, Outbox, now=later) is None


def test_failed_delivery_remains_pending(notification_db):
    from bovie.notifications import Delivery, accept
    from bovie.queue import claim, finish, retry_later

    accept(notification_db, event())
    now = datetime.now(UTC) + timedelta(seconds=1)
    first = claim(notification_db, Delivery, now=now)
    assert first is not None
    assert retry_later(notification_db, Delivery, first, now=now)
    assert claim(notification_db, Delivery, now=now) is None
    second = claim(notification_db, Delivery, now=now + timedelta(seconds=61))
    assert second is not None
    assert second.attempts == 2
    assert finish(notification_db, Delivery, second, now=now + timedelta(seconds=61))
