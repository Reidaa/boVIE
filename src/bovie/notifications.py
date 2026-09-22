"""Notification storage has no dependency on source models or credentials."""

from datetime import UTC, datetime

import httpx
from sqlalchemy import JSON, String
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from bovie.db import UTCDateTime
from bovie.events import OfferDiscovered
from bovie.queue import QueueColumns, claim, finish, retry_later

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


def accept(engine: Engine, event: OfferDiscovered) -> bool:
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
        if saved is None or saved.payload != payload:
            raise ValueError("Event ID already belongs to a different payload")
        if session.get(Delivery, event_id) is not None:
            return False
        session.add(Delivery(event_id=event_id, payload=payload))
    return True


def discord_payload(event: OfferDiscovered) -> dict:
    offer = event.offer
    fields = [field.model_dump() for field in offer.fields]
    if not fields:
        fields = [
            {"name": "Entreprise", "value": offer.organization[:1024] or "N/A"},
            {"name": "Lieu", "value": f"{offer.city}, {offer.country}"[:1024]},
        ]
    # Discord's aggregate embed text limit is 6000 characters.
    remaining = 6000 - len(offer.title)
    bounded = []
    for field in fields:
        available = remaining - len(field["name"])
        if available <= 0:
            break
        field["value"] = field["value"][:available]
        remaining -= len(field["name"]) + len(field["value"])
        bounded.append(field)
    return {
        "username": "boVIE",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": offer.title,
                "url": str(offer.url),
                "color": 341401,
                "fields": bounded,
            }
        ],
    }


def deliver_one(engine: Engine, client: httpx.Client, webhook: str) -> bool:
    work = claim(engine, Delivery)
    if work is None:
        return False
    try:
        response = client.post(
            webhook,
            json=discord_payload(
                OfferDiscovered.model_validate(work.payload),
            ),
        )
        response.raise_for_status()
    except Exception:
        retry_later(engine, Delivery, work)
        raise
    finish(engine, Delivery, work)
    return True
