import uuid

from sqlmodel import Field, Session, SQLModel, create_engine, select

from bovie.env import env


class Job(SQLModel, table=True):
    __tablename__ = "bovie_job"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    offer_id: int

db = create_engine(env.DATABASE_URL.encoded_string())
SQLModel.metadata.create_all(db)

class JobOffer:
    @staticmethod
    def all():
        with Session(db) as session:
            stmt = select(Job)
            results = session.exec(stmt)
            ids = [job.offer_id for job in results]

        return ids
    
    @staticmethod
    def create(job_id: int):
        with Session(db) as session:
            j = Job(offer_id=job_id)
            session.add(j)

            session.commit()

    @staticmethod
    def create_many(ids: list[int]):
        with Session(db) as session:
            for job_id in ids:
                session.add(Job(offer_id=job_id))

            session.commit()