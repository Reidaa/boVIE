from abc import ABC, abstractmethod
from typing import Any

import httpx
from loguru import logger
from rich.console import Console
from rich.table import Table
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

import src.discord as discord
from src.discord.model import JobEmbed

from .model import Job


class JobWriter(ABC):
    @abstractmethod
    def write_one(self, job: Job):
        pass

    @abstractmethod
    def write_many(self, jobs: list[Job]):
        pass

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TerminalWriter(JobWriter):
    def __init__(self):
        super().__init__()
        self.out = ""

    def write_one(self, job):
        self.out += f"{job.missionTitle}\n"

    def write_many(self, jobs):
        for offer in jobs:
            self.write_one(offer)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.out:
            print(self.out[:-1])
        else:
            print("Nothing to display ...")


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

        self.payloads.append(payload)

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for payload in self.payloads:
            try:
                self._send(payload)
            except RetryError as e:
                logger.error(f"Failed to send Discord message: {str(e)}")


class RichWriter(JobWriter):
    def __init__(self):
        super().__init__()
        self._console = Console()
        self._table = Table(title="Latest VIE/VIA Offers", show_lines=True)

        self._table.add_column("Title", style="cyan")
        self._table.add_column("Company", style="magenta")
        self._table.add_column("Location", style="green")
        self._table.add_column("Start Date", style="blue")

    def write_one(self, job):
        return self.write_many([job])

    def write_many(self, jobs):
        """Display offers in a formatted table"""
        for offer in jobs:
            self._table.add_row(
                offer.missionTitle.strip(),
                offer.organizationName.strip(),
                f"{str(offer.cityName).strip()}, {offer.countryName.strip()}",
                offer.missionStartDate,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._console.print(self._table)
