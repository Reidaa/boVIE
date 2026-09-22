import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def database_factory():
    """Only explicitly configured disposable MySQL; never an application DSN."""
    url = os.environ.get("MYSQL_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MYSQL_TEST_ADMIN_URL to a disposable MySQL 8.4 server")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    databases = []

    def create(domain):
        from bovie.db import make_engine
        from bovie.migrate import upgrade

        name = f"bovie_test_{uuid4().hex}"
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4"))
        engine = make_engine(admin.url.set(database=name))
        databases.append((name, engine))
        upgrade(engine, domain)
        return engine

    yield create
    for name, engine in databases:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE `{name}`"))
    admin.dispose()


@pytest.fixture
def source_db(database_factory):
    return database_factory("source")


@pytest.fixture
def notification_db(database_factory):
    return database_factory("notification")
