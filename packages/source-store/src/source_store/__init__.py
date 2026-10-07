"""Each source owns a separate copy of this schema and its own credentials.

Collectors publish an event and wait for the broker acknowledgment before
recording the offer here. A crash in between republishes the same event ID on
the next run, and consumers drop the duplicate.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from job_contracts import OfferEvent
from job_database import UTCDateTime
from sqlalchemy import JSON, Integer, String, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_bin",
}


class SourceBase(DeclarativeBase):
    pass


class Offer(SourceBase):
    __tablename__ = "offers"
    __table_args__ = TABLE_OPTIONS
    source_offer_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    event_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    # Null for offers recorded before hashes existed.
    content_hash: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Checkpoint(SourceBase):
    __tablename__ = "checkpoints"
    __table_args__ = TABLE_OPTIONS
    scan: Mapped[str] = mapped_column(String(64), primary_key=True)
    offset: Mapped[int] = mapped_column(Integer)


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
        stmt = insert(Checkpoint).values(scan=scan, offset=offset)
        session.execute(stmt.on_duplicate_key_update(offset=stmt.inserted.offset))
