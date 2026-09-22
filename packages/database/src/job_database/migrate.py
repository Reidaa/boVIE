"""Run an owner's packaged Alembic history on an explicit connection."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine


def upgrade_schema(engine: Engine, path: Path) -> None:
    config = Config()
    config.set_main_option("path_separator", "os")
    config.set_main_option("script_location", str(path))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
