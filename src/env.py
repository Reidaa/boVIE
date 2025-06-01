from pydantic import BaseModel, Field, field_validator, SecretStr
from enum import Enum, IntEnum
import os
from dotenv import load_dotenv

load_dotenv(override=True)


class EnvEnum(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Env(BaseModel):
    DATABASE_URL: SecretStr
    PYTHON_ENV: EnvEnum


env = Env(
    DATABASE_URL=SecretStr(os.getenv("DATABASE_URL")),
    PYTHON_ENV=os.getenv("PYTHON_ENV").lower(),
)
