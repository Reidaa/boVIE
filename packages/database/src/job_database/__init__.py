"""Connection and UTC storage mechanics; no global engine or schema creation."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.engine import URL, Engine
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """MySQL DATETIME(6) stores UTC without a zone; Python receives aware UTC."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DATETIME(fsp=6))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamps must be timezone aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


def make_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        },
    )
