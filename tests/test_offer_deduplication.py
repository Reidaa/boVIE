import asyncio

import pytest

from bovie import main as bovie_main
from bovie.job.models.search import SearchParameters  # noqa: E402


class RecordingPublisher:
    def __init__(self) -> None:
        self.jobs = []

    async def publish_one(self, job) -> None:
        self.jobs.append(job)

    async def publish_many(self, jobs) -> None:
        for job in jobs:
            await self.publish_one(job)


def test_task_queues_each_offer_once_per_scrape(monkeypatch):
    jobs = {1: object(), 2: object()}
    fetched_ids = []

    def get_from_id(job_id: int):
        fetched_ids.append(job_id)
        return jobs[job_id]

    monkeypatch.setattr(bovie_main, "search_id", lambda params: [1, 1, 2])
    monkeypatch.setattr(bovie_main, "get_from_id", get_from_id)

    publisher = RecordingPublisher()

    asyncio.run(bovie_main.task(SearchParameters(), publisher=publisher))

    assert fetched_ids == [1, 2]
    assert publisher.jobs == [jobs[1], jobs[2]]


def test_task_raises_when_publish_fails(monkeypatch):
    job = object()

    class FailingPublisher:
        async def publish_one(self, job) -> None:
            raise RuntimeError("publish failed")

        async def publish_many(self, jobs) -> None:
            raise RuntimeError("publish failed")

    monkeypatch.setattr(bovie_main, "search_id", lambda params: [1])
    monkeypatch.setattr(bovie_main, "get_from_id", lambda job_id: job)

    with pytest.raises(RuntimeError, match="publish failed"):
        asyncio.run(bovie_main.task(SearchParameters(), publisher=FailingPublisher()))
