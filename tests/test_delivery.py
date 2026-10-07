from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from tests.test_storage import event


def test_duplicate_ingestion_creates_one_pending_delivery(notification_db):
    from notification_store import Delivery, Inbox, accept

    discovered = event()
    assert accept(notification_db, discovered)
    assert not accept(notification_db, discovered)
    with notification_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 1
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 1


def test_reused_event_id_for_another_offer_is_rejected(notification_db):
    from notification_store import accept

    discovered = event()
    accept(notification_db, discovered)
    with pytest.raises(ValueError, match="different offer"):
        accept(
            notification_db, discovered.model_copy(update={"source_offer_id": "other"})
        )


def test_republished_event_is_accepted_once(notification_db):
    from notification_store import Delivery, Inbox, accept

    assert accept(notification_db, event())
    later = datetime.now(UTC) + timedelta(hours=2)
    assert not accept(notification_db, event(observed_at=later))
    with notification_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 1
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 1


def test_only_discoveries_create_deliveries(notification_db):
    from notification_store import Delivery, Inbox, accept

    assert not accept(notification_db, event(type="updated"))
    assert not accept(notification_db, event(type="closed"))
    with notification_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 2
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 0


def test_lease_expiry_and_stale_completion(notification_db):
    from job_database.queue import claim, finish
    from notification_store import Delivery, accept

    accept(notification_db, event())
    now = datetime.now(UTC) + timedelta(seconds=1)
    first = claim(notification_db, Delivery, now=now, lease_seconds=10)
    assert first is not None
    assert claim(notification_db, Delivery, now=now) is None
    later = now + timedelta(seconds=11)
    second = claim(notification_db, Delivery, now=later)
    assert second is not None
    assert first.token != second.token
    assert not finish(notification_db, Delivery, first, now=later)
    assert finish(notification_db, Delivery, second, now=later)
    assert claim(notification_db, Delivery, now=later) is None


def test_failed_delivery_remains_pending(notification_db):
    from job_database.queue import claim, finish, retry_later
    from notification_store import Delivery, accept

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
