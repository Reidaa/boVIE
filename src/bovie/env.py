import os

from dotenv import load_dotenv
from pydantic import BaseModel, PostgresDsn

load_dotenv(override=True, interpolate=True)


class Env(BaseModel):
    DATABASE_URL: PostgresDsn

env = Env(DATABASE_URL=os.getenv("DATABASE_URL"))
