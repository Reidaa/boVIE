"""Migrate this owner's schema without importing another owner's models."""

from pathlib import Path

import click
from job_database import make_engine
from job_database.env import load_env
from job_database.migrate import upgrade_schema
from sqlalchemy.engine import Engine


def upgrade(engine: Engine, *, wait_timeout: float = 0) -> None:
    upgrade_schema(
        engine, Path(__file__).parent / "migrations", wait_timeout=wait_timeout
    )


@click.command()
@click.option(
    "--wait-timeout",
    default=0,
    type=click.FloatRange(min=0),
    help="Seconds to wait for database readiness before migrating.",
)
def cli(wait_timeout: float):
    """Apply this schema's migrations to DATABASE_URL."""
    engine = make_engine(load_env().database_url)
    try:
        upgrade(engine, wait_timeout=wait_timeout)
    finally:
        engine.dispose()
