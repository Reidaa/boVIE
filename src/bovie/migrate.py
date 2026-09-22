from pathlib import Path

import click
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from bovie.db import make_engine
from bovie.env import load_env


def upgrade(engine: Engine, domain: str) -> None:
    if domain not in {"source", "notification"}:
        raise ValueError("Unknown database ownership domain")
    path = Path(__file__).parent / "migrations"
    config = Config()
    config.set_main_option("path_separator", "os")
    config.set_main_option("script_location", str(path))
    config.set_main_option("version_locations", str(path / domain))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@click.command()
@click.argument("domain", type=click.Choice(["source", "notification"]))
def cli(domain: str):
    """Explicitly migrate the database selected by DATABASE_URL."""
    engine = make_engine(load_env().database_url)
    try:
        upgrade(engine, domain)
    finally:
        engine.dispose()
