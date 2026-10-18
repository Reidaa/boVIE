"""Each source owns a separate copy of this schema and its own credentials.

Collectors publish an event and wait for the broker acknowledgment before
recording the offer here. A crash in between republishes the same event ID on
the next run, and consumers drop the duplicate.

A scraper usually breaks silently: the source returns an empty result instead
of an error. Each checkpoint records when its scan last returned results, and
`require_recent_results` fails the run once that is older than MAX_SILENCE.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from mysql_common import UTCDateTime
from offer_events import OfferEvent
from sqlalchemy import JSON, Integer, String, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Collectors run every 2 hours, so this is 6 runs in a row without results.
MAX_SILENCE = timedelta(hours=12)

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_bin",
}


class CollectorStoreBase(DeclarativeBase):
    pass


class Offer(CollectorStoreBase):
    __tablename__ = "offers"
    __table_args__ = TABLE_OPTIONS
    source_offer_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    event_id: Mapped[str] = mapped_column(String(36), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Checkpoint(CollectorStoreBase):
    __tablename__ = "checkpoints"
    __table_args__ = TABLE_OPTIONS
    scan: Mapped[str] = mapped_column(String(64), primary_key=True)
    offset: Mapped[int] = mapped_column(Integer)
    results_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SourceSilent(RuntimeError):
    """The source returned no results for too long; its API may have changed."""


def seen(engine: Engine, source_offer_id: str) -> bool:
    with Session(engine) as session:
        return session.get(Offer, source_offer_id) is not None


def record_page(
    engine: Engine,
    published: Iterable[OfferEvent],
    observed: Iterable[str],
    scan: str,
    offset: int,
) -> None:
    """Record published offers, refresh last_seen_at for the page, and checkpoint.

    Call only after the broker acknowledged every event in `published`.
    """
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        for event in published:
            stmt = insert(Offer).values(
                source_offer_id=event.source_offer_id,
                observed_at=event.observed_at,
                event_id=str(event.event_id),
                payload=event.model_dump(mode="json"),
                content_hash=event.offer.content_hash,
                last_seen_at=now,
            )
            # A concurrent run may have recorded the same offer first; keep its row.
            session.execute(
                stmt.on_duplicate_key_update(source_offer_id=Offer.source_offer_id)
            )
        identities = list(observed)
        if identities:
            session.execute(
                update(Offer)
                .where(Offer.source_offer_id.in_(identities))
                .values(last_seen_at=now)
            )
        stmt = insert(Checkpoint).values(
            scan=scan, offset=offset, results_seen_at=now if identities else None
        )
        changes = {"offset": stmt.inserted.offset}
        if identities:
            changes["results_seen_at"] = stmt.inserted.results_seen_at
        session.execute(stmt.on_duplicate_key_update(**changes))


def require_recent_results(engine: Engine, scan: str) -> None:
    """Raise SourceSilent unless the scan returned results within MAX_SILENCE.

    Call at the end of each run, after the last `record_page`.
    """
    with Session(engine) as session:
        seen_at = session.scalar(
            select(Checkpoint.results_seen_at).where(Checkpoint.scan == scan)
        )
    if seen_at is None:
        raise SourceSilent("The source has not returned any results yet")
    if datetime.now(UTC) - seen_at > MAX_SILENCE:
        raise SourceSilent(f"The source has returned no results since {seen_at}")
