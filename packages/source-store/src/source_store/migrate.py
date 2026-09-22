"""Migrate this owner's schema without importing another owner's models."""

from pathlib import Path

import click
from job_database import make_engine
from job_database.env import load_env
from job_database.migrate import upgrade_schema
from sqlalchemy.engine import Engine


def upgrade(engine: Engine) -> None:
    upgrade_schema(engine, Path(__file__).parent / "migrations")


@click.command()
def cli():
    """Apply this schema's migrations to DATABASE_URL."""
    engine = make_engine(load_env().database_url)
    try:
        upgrade(engine)
    finally:
        engine.dispose()
