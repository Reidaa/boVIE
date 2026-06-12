import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import nats
from nats.aio.client import Client as NatsClient
from nats.js.api import RetentionPolicy, StorageType, StreamConfig
from nats.js.client import JetStreamContext
from nats.js.errors import NotFoundError
from pydantic import BaseModel, ConfigDict, Field

from .models.job import Job

DEFAULT_NATS_URL = "nats://localhost:4222"
DEFAULT_NATS_STREAM = "BOVIE_JOBS"
DEFAULT_NATS_JOB_SUBJECT = "jobs.discovered"


class JobPublisher(Protocol):
    async def publish_one(self, job: Job) -> None:
        pass

    async def publish_many(self, jobs: list[Job]) -> None:
        pass


class JobDiscoveredEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    source: str = "business-france-civiweb"
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        alias="discoveredAt",
    )
    offer_id: int = Field(alias="offerId")
    job: Job


@dataclass(frozen=True)
class NatsPublisherConfig:
    url: str = DEFAULT_NATS_URL
    stream: str = DEFAULT_NATS_STREAM
    subject: str = DEFAULT_NATS_JOB_SUBJECT


class NatsJobPublisher:
    def __init__(self, config: NatsPublisherConfig):
        self.config = config
        self._client: NatsClient | None = None
        self._jetstream: JetStreamContext | None = None

    async def __aenter__(self) -> "NatsJobPublisher":
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def connect(self) -> None:
        self._client = await nats.connect(self.config.url)
        self._jetstream = self._client.jetstream()
        await self._ensure_stream()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.drain()
            self._client = None
            self._jetstream = None

    async def publish_one(self, job: Job) -> None:
        jetstream = self._require_jetstream()
        event = JobDiscoveredEvent(offerId=job.id, job=job)
        payload = event.model_dump_json(by_alias=True).encode()
        await jetstream.publish(
            self.config.subject,
            payload,
            stream=self.config.stream,
            headers={"Nats-Msg-Id": f"{event.source}:{event.offer_id}"},
        )

    async def publish_many(self, jobs: list[Job]) -> None:
        for job in jobs:
            await self.publish_one(job)

    async def _ensure_stream(self) -> None:
        jetstream = self._require_jetstream()

        try:
            await jetstream.stream_info(self.config.stream)
        except NotFoundError:
            await jetstream.add_stream(
                StreamConfig(
                    name=self.config.stream,
                    subjects=[self.config.subject],
                    retention=RetentionPolicy.LIMITS,
                    storage=StorageType.FILE,
                    duplicate_window=86_400,
                )
            )

    def _require_jetstream(self) -> JetStreamContext:
        if self._jetstream is None:
            raise RuntimeError("NATS publisher is not connected")

        return self._jetstream


def job_event_json(job: Job) -> str:
    event = JobDiscoveredEvent(offerId=job.id, job=job)
    return json.dumps(event.model_dump(mode="json", by_alias=True))
