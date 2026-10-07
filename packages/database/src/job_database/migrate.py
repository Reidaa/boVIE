"""Run an owner's packaged Alembic history on an explicit connection."""

from pathlib import Path
from time import monotonic, sleep

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError


def wait_for_database(engine: Engine, timeout: float) -> Connection:
    deadline = monotonic() + timeout
    while True:
        try:
            return engine.connect()
        except OperationalError:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise
            sleep(min(2, remaining))


def upgrade_schema(engine: Engine, path: Path, *, wait_timeout: float = 0) -> None:
    config = Config()
    config.set_main_option("path_separator", "os")
    config.set_main_option("script_location", str(path))
    with wait_for_database(engine, wait_timeout) as connection, connection.begin():
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
