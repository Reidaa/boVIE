"""Short claims shared as mechanics, never as cross-database ORM state."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import JSON, Integer, String, func, or_, select, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from job_database import UTCDateTime


class QueueColumns:
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    claim_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


@dataclass(frozen=True)
class Claim:
    event_id: str
    token: str
    payload: dict
    attempts: int


def database_now(session: Session) -> datetime:
    return (
        session.execute(select(func.utc_timestamp(6))).scalar_one().replace(tzinfo=UTC)
    )


def claim(
    engine: Engine,
    model: type[QueueColumns],
    *,
    now: datetime | None = None,
    lease_seconds: int = 120,
) -> Claim | None:
    with Session(engine) as session, session.begin():
        now = now or database_now(session)
        row = session.scalar(
            select(model)
            .where(
                model.completed_at.is_(None),
                model.available_at <= now,
                or_(model.lease_until.is_(None), model.lease_until <= now),
            )
            .order_by(model.available_at, model.event_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        token = str(uuid4())
        row.claim_token = token
        row.lease_until = now + timedelta(seconds=lease_seconds)
        row.attempts += 1
        return Claim(row.event_id, token, row.payload, row.attempts)


def _owned(model, work, now):
    return (
        model.event_id == work.event_id,
        model.claim_token == work.token,
        model.completed_at.is_(None),
        model.lease_until > now,
    )


def finish(
    engine: Engine,
    model: type[QueueColumns],
    work: Claim,
    *,
    now: datetime | None = None,
) -> bool:
    with Session(engine) as session, session.begin():
        now = now or database_now(session)
        result = session.execute(
            update(model)
            .where(*_owned(model, work, now))
            .values(
                completed_at=now,
                claim_token=None,
                lease_until=None,
            )
        )
        return cast(CursorResult, result).rowcount == 1


def retry_later(
    engine: Engine,
    model: type[QueueColumns],
    work: Claim,
    *,
    now: datetime | None = None,
    delay_seconds: float | None = None,
) -> bool:
    delay = (
        delay_seconds
        if delay_seconds is not None
        else min(3600, 5 * 2 ** min(work.attempts, 10))
    )
    with Session(engine) as session, session.begin():
        now = now or database_now(session)
        result = session.execute(
            update(model)
            .where(*_owned(model, work, now))
            .values(
                available_at=now + timedelta(seconds=delay),
                claim_token=None,
                lease_until=None,
            )
        )
        return cast(CursorResult, result).rowcount == 1
