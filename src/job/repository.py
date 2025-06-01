import uuid
from abc import ABC, abstractmethod
from typing import List

from sqlmodel import Field, Session, SQLModel, create_engine, select
from src.env import env


class Job(SQLModel, table=True):
    __tablename__ = "bovie_job"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_id: int


class JobRepository(ABC):
    @abstractmethod
    def list(self) -> List[int]:
        pass

    @abstractmethod
    def insert(self, id: int) -> None:
        pass

    @abstractmethod
    def insert_many(self, ids: List[int]) -> None:
        pass


class FileRepository(JobRepository):
    def __init__(self):
        super().__init__()
        self._engine = create_engine(env.DATABASE_URL.get_secret_value())

        SQLModel.metadata.create_all(self._engine)

    def list(self):
        with Session(self._engine) as session:
            stmt = select(Job)
            results = session.exec(stmt)
            ids = [job.offer_id for job in results]

        return ids

    def insert(self, job_id: int):
        with Session(self._engine) as session:
            j = Job(offer_id=job_id)
            session.add(j)

            session.commit()

    def insert_many(self, ids: List[int]):
        with Session(self._engine) as session:
            for job_id in ids:
                session.add(Job(offer_id=job_id))

            session.commit()
