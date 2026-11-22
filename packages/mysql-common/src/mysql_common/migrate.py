"""Run an owner's packaged Alembic history on an explicit connection."""

import logging
from pathlib import Path
from time import monotonic, sleep

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

from mysql_common import make_engine

log = logging.getLogger(__name__)

# MySQL error for a database that does not exist. The server answered, so it is ready.
UNKNOWN_DATABASE = 1049


def _is_unknown_database(error: OperationalError) -> bool:
    args = getattr(error.orig, "args", ())
    return bool(args) and args[0] == UNKNOWN_DATABASE


def wait_for_database(engine: Engine, timeout: float) -> Connection:
    """Connect, retrying until the server answers or `timeout` seconds pass.

    A missing database means the server is up; that error is raised at once.
    """
    deadline = monotonic() + timeout
    while True:
        try:
            return engine.connect()
        except OperationalError as error:
            remaining = deadline - monotonic()
            if _is_unknown_database(error) or remaining <= 0:
                raise
            sleep(min(2, remaining))


def create_database(engine: Engine) -> None:
    """Create the database named in the engine URL, with the collation of local Compose."""
    name = engine.url.database
    if not name:
        raise ValueError("The database URL names no database")
    # URL.set() ignores None, so clear the database through the NamedTuple API.
    server = make_engine(engine.url._replace(database=None))
    quoted = server.dialect.identifier_preparer.quote_identifier(name)
    try:
        with server.connect() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS {quoted}"
                    " CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin"
                )
            )
    finally:
        server.dispose()
    log.info("Created database %s", name)


def _connect(engine: Engine, timeout: float) -> Connection:
    try:
        return wait_for_database(engine, timeout)
    except OperationalError as error:
        if not _is_unknown_database(error):
            raise
    create_database(engine)
    return engine.connect()


def upgrade_schema(engine: Engine, path: Path, *, wait_timeout: float = 0) -> None:
    """Migrate to head. Creates the database in the URL first when it is missing."""
    config = Config()
    config.set_main_option("path_separator", "os")
    config.set_main_option("script_location", str(path))
    with _connect(engine, wait_timeout) as connection, connection.begin():
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
