from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from tests.test_storage import event


def test_duplicate_ingestion_creates_one_pending_delivery(discord_db):
    from discord_store import Delivery, Inbox, accept

    discovered = event()
    assert accept(discord_db, discovered)
    assert not accept(discord_db, discovered)
    with discord_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 1
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 1


def test_reused_event_id_for_another_offer_is_rejected(discord_db):
    from discord_store import accept

    discovered = event()
    accept(discord_db, discovered)
    with pytest.raises(ValueError, match="different offer"):
        accept(discord_db, discovered.model_copy(update={"source_offer_id": "other"}))


def test_republished_event_is_accepted_once(discord_db):
    from discord_store import Delivery, Inbox, accept

    assert accept(discord_db, event())
    later = datetime.now(UTC) + timedelta(hours=2)
    assert not accept(discord_db, event(observed_at=later))
    with discord_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 1
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 1


def test_only_discoveries_create_deliveries(discord_db):
    from discord_store import Delivery, Inbox, accept

    assert not accept(discord_db, event(type="updated"))
    assert not accept(discord_db, event(type="closed"))
    with discord_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Inbox)) == 2
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 0


def test_lease_expiry_and_stale_completion(discord_db):
    from discord_store import Delivery, accept
    from mysql_common.queue import claim, finish

    accept(discord_db, event())
    now = datetime.now(UTC) + timedelta(seconds=1)
    first = claim(discord_db, Delivery, now=now, lease_seconds=10)
    assert first is not None
    assert claim(discord_db, Delivery, now=now) is None
    later = now + timedelta(seconds=11)
    second = claim(discord_db, Delivery, now=later)
    assert second is not None
    assert first.token != second.token
    assert not finish(discord_db, Delivery, first, now=later)
    assert finish(discord_db, Delivery, second, now=later)
    assert claim(discord_db, Delivery, now=later) is None


def test_failed_delivery_remains_pending(discord_db):
    from discord_store import Delivery, accept
    from mysql_common.queue import claim, finish, retry_later

    accept(discord_db, event())
    now = datetime.now(UTC) + timedelta(seconds=1)
    first = claim(discord_db, Delivery, now=now)
    assert first is not None
    assert retry_later(discord_db, Delivery, first, now=now)
    assert claim(discord_db, Delivery, now=now) is None
    second = claim(discord_db, Delivery, now=now + timedelta(seconds=61))
    assert second is not None
    assert second.attempts == 2
    assert finish(discord_db, Delivery, second, now=now + timedelta(seconds=61))
