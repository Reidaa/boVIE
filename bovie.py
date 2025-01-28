#!/usr/bin/env python3
"""
Bovie - A tool to discover VIE/VIA opportunities from Business France
"""

import logging
import os
import sys
import time
from typing import Dict, List

import click
from dotenv import load_dotenv

from src.businessFrance.enum import Regions, Specializations
from src.businessFrance.models import Offer, SearchParameters
from src.businessFrance.OfferService import OfferService
from src.repository.BaseRepository import BaseRepository
from src.repository.InMemoryRepository import InMemoryRepository
from src.repository.SimpleRepository import SimpleRepository
from src.writer.DiscordWriter import DiscordWriter
from src.writer.TerminalWriter import TerminalWriter

load_dotenv(override=True)

repoFactory: Dict[str, BaseRepository] = {
    "memory": InMemoryRepository,
    "file": SimpleRepository,
}

DEFAULT_BOVIE_OFFER_MAX = 25
DEFAULT_BOVIE_STORAGE_TYPE = "file"
DEFAULT_BOVIE_CONTINUOUS = False
DEFAULT_BOVIE_SLEEP_DURATION = 60
DEFAULT_DISCORD_WEBHOOK_URL = None


class OfferFetcher:
    """Handles fetching offers from Business France API"""

    def __init__(self):
        self._service = OfferService("https://civiweb-api-prd.azurewebsites.net/api")

    def fetch_offers(self, limit: int) -> List[Offer]:
        """Fetch latest VIE/VIA offers"""
        self.search_params = SearchParameters(
            limit=limit,
            specializationsIds=[
                Specializations.INFORMATION_SYSTEMS.value,
                Specializations.SCIENTIFIC_AND_INDUSTRIAL_COMPUTING.value,
            ],
            gerographicZones=[
                Regions.ASIA_PACIFIC.value,
                Regions.NORTH_AMERICA.value,
                Regions.SOUTH_AMERICA.value,
                Regions.WESTERN_EUROPE.value,
            ],
        )
        offers = self._service.search(params=self.search_params)

        return offers

    def fetch(self, id: int) -> Offer:
        return self._service.details(id)


@click.command()
@click.option(
    "--webhook-url",
    default=os.environ.get("DISCORD_WEBHOOK_URL", DEFAULT_DISCORD_WEBHOOK_URL),
    type=click.STRING,
    help="Discord webhook URL",
)
@click.option(
    "--limit",
    default=os.environ.get("BOVIE_OFFER_MAX", DEFAULT_BOVIE_OFFER_MAX),
    type=click.INT,
    help=f"Maximum number of offers to fetch (default: {DEFAULT_BOVIE_OFFER_MAX})",
)
@click.option(
    "--storage-type",
    default=os.environ.get("BOVIE_STORAGE_TYPE", DEFAULT_BOVIE_STORAGE_TYPE),
    type=click.Choice(["memory", "file"], case_sensitive=False),
    help=f"Storage backend to use: 'file' or 'memory' (default: {DEFAULT_BOVIE_STORAGE_TYPE})",
)
@click.option(
    "--continuous",
    default=os.environ.get("BOVIE_CONTINUOUS", DEFAULT_BOVIE_CONTINUOUS),
    type=click.BOOL,
    help=f"Run in continuous mode, checking for new offers periodically (default: {DEFAULT_BOVIE_CONTINUOUS})",
)
@click.option(
    "--sleep-duration",
    default=os.environ.get("BOVIE_SLEEP_DURATION", DEFAULT_BOVIE_SLEEP_DURATION),
    type=click.IntRange(min=1, max_open=True),
    help=f"Interval between checks in continuous mode, in seconds (default: {DEFAULT_BOVIE_SLEEP_DURATION})",
)
def bot(
    webhook_url: str,
    limit: int,
    storage_type: str,
    continuous: bool,
    sleep_duration: int,
):
    fetcher = OfferFetcher()
    notifier = DiscordWriter(webhook_url)
    repository: BaseRepository = repoFactory[storage_type]()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger("bovie")

    logger.info("Starting ...")

    def task():
        try:
            ids = fetcher.fetch_offers(limit)
            for id in ids:
                if id in repository.read():
                    continue
                # Let's go easy on them
                time.sleep(0.5)
                offer = fetcher.fetch(id)
                ok = notifier.write(offer)
                if ok:
                    repository.insert(offer.id)
                    logger.info(f"Posted new offer: {offer.missionTitle}")
        except Exception as e:
            logger.error(f"Error in bot execution: {str(e)}")
            raise Exception

    if not continuous:
        task()
    else:
        while True:
            logger.info(f"Set to wake up every {sleep_duration} seconds")
            logger.info("Waking Up ...")
            task()
            logger.info("Going to sleep. Zzz")
            time.sleep(sleep_duration)


@click.command()
@click.option(
    "--limit",
    default=os.environ.get("BOVIE_OFFER_MAX", DEFAULT_BOVIE_OFFER_MAX),
    type=click.INT,
    help=f"Maximum offers to fetch (default: {DEFAULT_BOVIE_OFFER_MAX})",
)
def pull(limit: int):
    fetcher = OfferFetcher()
    notifier = TerminalWriter()

    try:
        ids = fetcher.fetch_offers(limit)
        offers = [fetcher.fetch(id) for id in ids]
    except Exception:
        return 1

    notifier.write_many(offers=offers)


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(pull)
    cli.add_command(bot)
    cli()
