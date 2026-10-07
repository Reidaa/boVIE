import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from mysql_common.env import Env
from pydantic import HttpUrl, ValidationError
from sqlalchemy import func, select


def test_mysql_configuration():
    settings = Env(DATABASE_URL="mysql+pymysql://worker:secret@localhost/source")
    assert settings.database_url.drivername == "mysql+pymysql"
    assert "secret" not in repr(settings)
    railway = Env(DATABASE_URL="mysql://worker:p%40ss@localhost/source")
    assert railway.database_url.drivername == "mysql+pymysql"
    assert railway.database_url.password == "p@ss"
    for url in ("postgresql://u:p@host/db", "sqlite://", "mysql://u:p@host"):
        with pytest.raises(ValidationError):
            Env(DATABASE_URL=url)


def test_imports_do_not_open_database():
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sqlalchemy
def forbidden(*args, **kwargs):
    raise AssertionError('Import attempted to create an engine')
sqlalchemy.create_engine = forbidden
import mysql_common.env, mysql_common, collector_business_france.main
""",
        ],
        env=environment,
        check=True,
    )


def event(offer_id="ABC", **changes):
    from offer_events import OfferDetails, OfferEvent

    fields: dict[str, Any] = {
        "type": "discovered",
        "source": "business_france",
        "source_offer_id": offer_id,
        "observed_at": datetime.now(UTC),
        "offer": OfferDetails(
            title="Engineer",
            organization="Example",
            country="France",
            city="Paris",
            url=HttpUrl("https://example.com/jobs/abc"),
        ),
    }
    return OfferEvent(**(fields | changes))


def test_event_ids_are_stable_across_republishing():
    first = event()
    assert event().event_id == first.event_id
    assert event(observed_at=datetime(2026, 1, 1, tzinfo=UTC)).event_id == (
        first.event_id
    )
    assert event("other").event_id != first.event_id
    assert event(type="closed").event_id != first.event_id
    assert event(source="wttj").event_id != first.event_id


def test_update_event_ids_follow_offer_content():
    update = event(type="updated")
    assert event(type="updated").event_id == update.event_id
    changed = event(type="updated").offer.model_copy(update={"title": "Lead"})
    assert event(type="updated", offer=changed).event_id != update.event_id


def test_recorded_offers_keep_content_hash_and_sightings(collector_db):
    from collector_store import Checkpoint, Offer, record_page, seen
    from sqlalchemy.orm import Session

    discovered = event()
    record_page(collector_db, [discovered], [discovered.source_offer_id], "scan", 1)
    record_page(collector_db, [discovered, event("abc")], ["ABC", "abc"], "scan", 2)
    assert seen(collector_db, "ABC") and seen(collector_db, "abc")
    with Session(collector_db) as session:
        assert session.scalar(select(func.count()).select_from(Offer)) == 2
        offer = session.get(Offer, "ABC")
        assert offer is not None
        assert offer.event_id == str(discovered.event_id)
        assert offer.content_hash == discovered.offer.content_hash
        assert offer.observed_at == discovered.observed_at
        assert offer.last_seen_at is not None
        first_sighting = offer.last_seen_at
        checkpoint = session.get(Checkpoint, "scan")
        assert checkpoint is not None and checkpoint.offset == 2
    record_page(collector_db, [], ["ABC", "unrecorded"], "scan", 3)
    with Session(collector_db) as session:
        offer = session.get(Offer, "ABC")
        assert offer is not None and offer.last_seen_at is not None
        assert offer.last_seen_at > first_sighting
        assert session.get(Offer, "unrecorded") is None


def test_failed_page_rolls_back_offers_and_checkpoint(collector_db):
    from collector_store import Checkpoint, Offer, record_page

    def broken_events():
        yield event()
        raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        record_page(collector_db, broken_events(), [], "scan", 1)
    with collector_db.connect() as conn:
        for table in (Offer, Checkpoint):
            assert conn.scalar(select(func.count()).select_from(table)) == 0


def test_concurrent_recording_keeps_one_offer(collector_db):
    from concurrent.futures import ThreadPoolExecutor

    from collector_store import Offer, record_page

    with ThreadPoolExecutor(max_workers=4) as workers:
        list(
            workers.map(
                lambda _: record_page(collector_db, [event()], ["ABC"], "scan", 1),
                range(4),
            )
        )
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 1


@pytest.mark.parametrize("owner", [0, 1, 2])
def test_domain_credentials_cannot_access_other_domains(database_factory, owner):
    from uuid import uuid4

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    domains = [
        (database_factory("collector"), "offers"),
        (database_factory("collector"), "offers"),
        (database_factory("discord"), "inbox"),
    ]
    first, own_table = domains[owner]
    user = "bovie_test_" + uuid4().hex[:20]
    password = uuid4().hex
    admin = create_engine(first.url.set(database="mysql"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql("CREATE USER %s IDENTIFIED BY %s", (user, password))
            conn.exec_driver_sql(
                f"GRANT ALL ON `{first.url.database}`.* TO %s", (user,)
            )
        restricted = create_engine(first.url.set(username=user, password=password))
        try:
            with restricted.connect() as conn:
                assert conn.scalar(text(f"SELECT COUNT(*) FROM {own_table}")) == 0
                for index, (engine, table) in enumerate(domains):
                    if index == owner:
                        continue
                    with pytest.raises(DBAPIError):
                        conn.execute(
                            text(f"SELECT * FROM `{engine.url.database}`.{table}")
                        )
        finally:
            restricted.dispose()
    finally:
        with admin.connect() as conn:
            conn.exec_driver_sql("DROP USER IF EXISTS %s", (user,))
        admin.dispose()
