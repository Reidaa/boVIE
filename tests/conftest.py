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
        from collector_store.migrate import upgrade as upgrade_collector
        from discord_store.migrate import upgrade as upgrade_discord
        from mysql_common import make_engine

        name = f"bovie_test_{uuid4().hex}"
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4"))
        engine = make_engine(admin.url.set(database=name))
        databases.append((name, engine))
        (upgrade_collector if domain == "collector" else upgrade_discord)(engine)
        return engine

    yield create
    for name, engine in databases:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE `{name}`"))
    admin.dispose()


@pytest.fixture
def collector_db(database_factory):
    return database_factory("collector")


@pytest.fixture
def discord_db(database_factory):
    return database_factory("discord")
