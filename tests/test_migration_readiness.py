from time import monotonic
from unittest.mock import Mock
from uuid import uuid4

import pytest
from mysql_common import make_engine, migrate
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


@pytest.fixture
def database_name(mysql_admin):
    """A database name that does not exist yet; the database is dropped afterwards."""
    # The hyphen needs identifier quoting in CREATE DATABASE.
    name = f"bovie-test-{uuid4().hex}"
    yield name
    with mysql_admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS `{name}`"))


def test_migration_creates_a_missing_database(mysql_admin, database_name):
    from collector_store.migrate import upgrade

    name = database_name
    engine = make_engine(mysql_admin.url.set(database=name))
    started = monotonic()
    try:
        upgrade(engine, wait_timeout=20)
    finally:
        engine.dispose()
    assert monotonic() - started < 20
    with mysql_admin.connect() as conn:
        assert conn.execute(
            text(
                "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME"
                " FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = :name"
            ),
            {"name": name},
        ).one() == ("utf8mb4", "utf8mb4_0900_bin")
        assert conn.scalar(text(f"SELECT COUNT(*) FROM `{name}`.offers")) == 0


def test_database_readiness_retries_connection_failures(monkeypatch):
    engine = Mock()
    connection = Mock()
    engine.connect.side_effect = [OperationalError(None, None, Exception()), connection]
    monkeypatch.setattr(migrate, "monotonic", lambda: 0)
    pause = Mock()
    monkeypatch.setattr(migrate, "sleep", pause)
    assert migrate.wait_for_database(engine, 10) is connection
    assert engine.connect.call_count == 2
    pause.assert_called_once_with(2)


def test_database_readiness_deadline_is_bounded(monkeypatch):
    engine = Mock()
    engine.connect.side_effect = OperationalError(None, None, Exception())
    times = iter([0, 2, 3])
    monkeypatch.setattr(migrate, "monotonic", lambda: next(times))
    pause = Mock()
    monkeypatch.setattr(migrate, "sleep", pause)
    with pytest.raises(OperationalError):
        migrate.wait_for_database(engine, 3)
    assert engine.connect.call_count == 2
    pause.assert_called_once_with(1)


def test_migration_errors_are_not_retried(monkeypatch, tmp_path):
    engine = Mock()
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    transaction = Mock()
    transaction.__enter__ = Mock()
    transaction.__exit__ = Mock(return_value=False)
    connection.begin.return_value = transaction
    engine.connect.return_value = connection
    upgrade = Mock(side_effect=OperationalError(None, None, Exception()))
    monkeypatch.setattr(migrate.command, "upgrade", upgrade)
    with pytest.raises(OperationalError):
        migrate.upgrade_schema(engine, tmp_path, wait_timeout=10)
    engine.connect.assert_called_once()
    upgrade.assert_called_once()
