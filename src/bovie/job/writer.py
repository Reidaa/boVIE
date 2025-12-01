from abc import ABC, abstractmethod
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import bovie.discord as discord
from bovie.discord.model import JobEmbed

from .models import Job


class JobWriter(ABC):
    @abstractmethod
    def write_one(self, job: Job):
        pass

    @abstractmethod
    def write_many(self, jobs: list[Job]):
        pass


class TerminalWriter(JobWriter):
    def __init__(self):
        super().__init__()
        self.out = ""

    def write_one(self, job):
        logger.info(f"New offer: {job.missionTitle}")

    def write_many(self, jobs):
        for offer in jobs:
            self.write_one(offer)


class DiscordWriter(JobWriter):
    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url
        self.payloads: list[dict[str, Any]] = []

    def write_one(self, job):
        payload = {
            "content": "",
            "tts": False,
            "embeds": [JobEmbed(job).to_dict()],
            "components": [],
            "actions": {},
        }

        self._send(payload)

    def write_many(self, jobs):
        for job in jobs:
            self.write_one(job)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _send(self, payload: dict):
        payload_id = payload["embeds"][0]["title"]
        r = discord.CLIENT.post(url=self.webhook_url, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send Discord message {payload_id}: {str(e)}")
            raise e
        else:
            logger.debug(f"Message sent {payload_id}")
