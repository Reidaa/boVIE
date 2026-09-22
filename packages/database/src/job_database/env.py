"""Configuration is loaded only by process entrypoints."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.engine import URL, make_url


class Env(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    DATABASE_URL: str = Field(repr=False)

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_mysql(cls, value: str) -> str:
        try:
            url = make_url(value)
        except Exception:
            raise ValueError("DATABASE_URL must be a MySQL SQLAlchemy URL") from None
        if url.drivername != "mysql+pymysql" or not all(
            (url.host, url.username, url.database)
        ):
            raise ValueError("Use mysql+pymysql://user:password@host/database")
        return value

    @property
    def database_url(self) -> URL:
        return make_url(self.DATABASE_URL)


def load_env() -> Env:
    load_dotenv(".env", override=False)
    return Env(DATABASE_URL=os.environ.get("DATABASE_URL", ""))
