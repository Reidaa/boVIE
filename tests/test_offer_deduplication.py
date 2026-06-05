import os

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/database",
)

from bovie import db as bovie_db  # noqa: E402
from bovie import main as bovie_main  # noqa: E402
from bovie.db import JobOffer  # noqa: E402
from bovie.job.models.search import SearchParameters  # noqa: E402


class RecordingWriter:
    def __init__(self) -> None:
        self.jobs = []

    def write_one(self, job) -> None:
        self.jobs.append(job)

    def write_many(self, jobs) -> None:
        for job in jobs:
            self.write_one(job)


@pytest.fixture
def in_memory_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(bovie_db, "db", engine)

    yield engine

    SQLModel.metadata.drop_all(engine)


def test_job_offer_create_ignores_duplicate_offer_ids(in_memory_db):
    assert JobOffer.create(123) is True
    assert JobOffer.create(123) is False

    assert JobOffer.exists(123) is True
    assert JobOffer.all() == [123]


def test_task_records_offer_once_after_all_writers_succeed(monkeypatch):
    jobs = {1: object(), 2: object()}
    fetched_ids = []

    class FakeJobOffer:
        seen = {99}
        created = []

        @classmethod
        def exists(cls, job_id: int) -> bool:
            return job_id in cls.seen

        @classmethod
        def create(cls, job_id: int) -> bool:
            if job_id in cls.seen:
                return False

            cls.seen.add(job_id)
            cls.created.append(job_id)
            return True

    def get_from_id(job_id: int):
        fetched_ids.append(job_id)
        return jobs[job_id]

    monkeypatch.setattr(bovie_main, "JobOffer", FakeJobOffer)
    monkeypatch.setattr(bovie_main, "search_id", lambda params: [1, 1, 2, 99])
    monkeypatch.setattr(bovie_main, "get_from_id", get_from_id)

    writer_a = RecordingWriter()
    writer_b = RecordingWriter()

    bovie_main.task(SearchParameters(), writers=[writer_a, writer_b])

    assert fetched_ids == [1, 2]
    assert writer_a.jobs == [jobs[1], jobs[2]]
    assert writer_b.jobs == [jobs[1], jobs[2]]
    assert FakeJobOffer.created == [1, 2]


def test_task_does_not_record_offer_when_writer_fails(monkeypatch):
    job = object()

    class FakeJobOffer:
        created = []

        @staticmethod
        def exists(job_id: int) -> bool:
            return False

        @classmethod
        def create(cls, job_id: int) -> bool:
            cls.created.append(job_id)
            return True

    class FailingWriter:
        def write_one(self, job) -> None:
            raise RuntimeError("writer failed")

    monkeypatch.setattr(bovie_main, "JobOffer", FakeJobOffer)
    monkeypatch.setattr(bovie_main, "search_id", lambda params: [1])
    monkeypatch.setattr(bovie_main, "get_from_id", lambda job_id: job)

    with pytest.raises(RuntimeError, match="writer failed"):
        bovie_main.task(SearchParameters(), writers=[FailingWriter()])

    assert FakeJobOffer.created == []
