"""Each source owns a separate copy of this schema and its own credentials."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import JSON, Integer, String
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from bovie.db import UTCDateTime
from bovie.events import OfferDiscovered
from bovie.queue import QueueColumns

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


class Outbox(QueueColumns, SourceBase):
    __tablename__ = "outbox"
    __table_args__ = TABLE_OPTIONS


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
    events: Iterable[OfferDiscovered],
    scan: str,
    offset: int,
) -> list[OfferDiscovered]:
    discovered = []
    with Session(engine) as session, session.begin():
        for event in events:
            payload = event.model_dump(mode="json")
            event_id = str(event.event_id)
            stmt = insert(Offer).values(
                source_offer_id=event.source_offer_id,
                observed_at=event.observed_at,
                event_id=event_id,
                payload=payload,
            )
            session.execute(
                stmt.on_duplicate_key_update(
                    source_offer_id=Offer.source_offer_id,
                )
            )
            saved = session.get(Offer, event.source_offer_id, populate_existing=True)
            if saved is None:
                raise ValueError("Event ID already belongs to a different offer")
            if saved.event_id == event_id:
                outbox = insert(Outbox).values(event_id=event_id, payload=payload)
                session.execute(
                    outbox.on_duplicate_key_update(
                        event_id=outbox.inserted.event_id,
                    )
                )
                discovered.append(event)
        stmt = insert(Checkpoint).values(scan=scan, offset=offset)
        session.execute(stmt.on_duplicate_key_update(offset=stmt.inserted.offset))
    return discovered
