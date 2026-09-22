from unittest.mock import Mock

import pytest
from job_database import migrate
from sqlalchemy.exc import OperationalError


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
