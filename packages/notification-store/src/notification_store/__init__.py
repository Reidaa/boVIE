"""Notification schema and atomic inbox acceptance."""

from datetime import UTC, datetime

from job_contracts import OfferEvent
from job_database import UTCDateTime
from job_database.queue import QueueColumns
from sqlalchemy import JSON, String
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_bin",
}


class NotificationBase(DeclarativeBase):
    pass


class Inbox(NotificationBase):
    __tablename__ = "inbox"
    __table_args__ = TABLE_OPTIONS
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Delivery(QueueColumns, NotificationBase):
    __tablename__ = "deliveries"
    __table_args__ = TABLE_OPTIONS


def identity(payload: dict) -> tuple:
    # Events written before the type field existed were all discoveries.
    return (
        payload["source"],
        payload["source_offer_id"],
        payload.get("type", "discovered"),
    )


def accept(engine: Engine, event: OfferEvent) -> bool:
    """Store the event once and queue a Discord delivery for new discoveries.

    A republished event keeps its ID but can carry a later observed_at, so
    duplicates are matched on the offer identity, not on the whole payload.
    """
    payload = event.model_dump(mode="json")
    event_id = str(event.event_id)
    with Session(engine) as session, session.begin():
        stmt = insert(Inbox).values(
            event_id=event_id,
            payload=payload,
            received_at=datetime.now(UTC),
        )
        session.execute(stmt.on_duplicate_key_update(event_id=stmt.inserted.event_id))
        saved = session.get(Inbox, event_id, populate_existing=True)
        if saved is None or identity(saved.payload) != identity(payload):
            raise ValueError("Event ID already belongs to a different offer")
        if event.type != "discovered" or session.get(Delivery, event_id) is not None:
            return False
        session.add(Delivery(event_id=event_id, payload=payload))
    return True
