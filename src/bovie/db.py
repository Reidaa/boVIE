import uuid

from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, create_engine, select

from bovie.env import env

UNIQUE_OFFER_ID_CONSTRAINT = "uq_bovie_job_offer_id"


class Job(SQLModel, table=True):
    __tablename__ = "bovie_job"
    __table_args__ = (
        UniqueConstraint("offer_id", name=UNIQUE_OFFER_ID_CONSTRAINT),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_id: int


db = create_engine(env.DATABASE_URL.encoded_string())


class JobOffer:
    @staticmethod
    def all() -> list[int]:
        with Session(db) as session:
            stmt = select(Job)
            results = session.exec(stmt)
            ids = [job.offer_id for job in results]

        return ids

    @staticmethod
    def exists(job_id: int) -> bool:
        with Session(db) as session:
            stmt = select(Job).where(Job.offer_id == job_id)
            return session.exec(stmt).first() is not None

    @staticmethod
    def create(job_id: int) -> bool:
        with Session(db) as session:
            j = Job(offer_id=job_id)
            session.add(j)

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False

        return True

    @staticmethod
    def create_many(ids: list[int]) -> int:
        return sum(1 for job_id in ids if JobOffer.create(job_id))