import uuid

from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = "bovie_job"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_id: int