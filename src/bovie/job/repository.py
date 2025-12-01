from abc import ABC, abstractmethod
from typing import List

from sqlmodel import Session, SQLModel, create_engine, select

from bovie.db import Job
from bovie.env import env


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


class DBRepository(JobRepository):
    def __init__(self):
        super().__init__()
        self._engine = create_engine(env.DATABASE_URL.encoded_string())

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
