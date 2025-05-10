#!/usr/bin/env python3
"""
Bovie - A tool to discover VIE/VIA opportunities from Business France
"""

import os
import sys
import time

import click
from dotenv import load_dotenv
from loguru import logger

import src.job as job
from src.job.repository import FileRepository
from src.job.writer import DiscordWriter, RichWriter, TerminalWriter

load_dotenv(override=True)

ENV = os.environ.get("ENVIRONMENT", "development").lower()
if ENV == "production":
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    logger.add(sys.stdout, level="WARNING")
    logger.add(sys.stdout, level="ERROR")

DEFAULT_BOVIE_OFFER_MAX = 25
DEFAULT_BOVIE_CONTINUOUS = False
DEFAULT_BOVIE_SLEEP_DURATION = 60
DEFAULT_DISCORD_WEBHOOK_URL = ""
DEFAULT_NOTIFIER = "terminal"
DEFAULT_QUIET = False

@click.command()
@click.option(
    "--webhook-url",
    default=DEFAULT_DISCORD_WEBHOOK_URL,
    type=click.STRING,
    help="Discord webhook URL",
    envvar="DISCORD_WEBHOOK_URL",
)
@click.option(
    "--limit",
    default=DEFAULT_BOVIE_OFFER_MAX,
    type=click.INT,
    show_default=DEFAULT_BOVIE_OFFER_MAX,
    envvar="BOVIE_OFFER_MAX",
)
@click.option(
    "--sleep-duration",
    default=DEFAULT_BOVIE_SLEEP_DURATION,
    type=click.INT,
    show_default=DEFAULT_BOVIE_SLEEP_DURATION,
    envvar="BOVIE_SLEEP_DURATION",
)
@click.option(
    "--notifier",
    default=DEFAULT_NOTIFIER,
    type=click.Choice(["terminal", "rich", "discord"], case_sensitive=False),
    show_default=DEFAULT_NOTIFIER,
    envvar="BOVIE_NOTIFIER",
)
@click.option(
    "--continuous",
    default=DEFAULT_BOVIE_CONTINUOUS,
    type=click.BOOL,
    is_flag=True,
    show_default=DEFAULT_BOVIE_CONTINUOUS,
    envvar="BOVIE_CONTINUOUS",
)
@click.option(
    "--quiet",
    default=DEFAULT_QUIET,
    type=click.BOOL,
    is_flag=True,
    show_default=DEFAULT_QUIET,
    envvar="BOVIE_QUIET",
)
def cli(
    webhook_url: str,
    limit: int,
    sleep_duration: int,
    notifier: str,
    continuous: bool,
    quiet: bool,
):
    params = job.DEFAULT_SEARCH_PARAMS
    params.limit = limit
    repository = FileRepository()

    if quiet:
        logger.remove()

    WriterFactory = {
        "terminal": TerminalWriter(),
        "discord": DiscordWriter(webhook_url),
        "rich": RichWriter(),
    }

    def task():
        try:
            ids = job.search_id(params)
            with WriterFactory[notifier] as writer:
                for id in ids:
                    if id in repository.list():
                        continue
                    j = job.get_by_id(id)
                    if not j:
                        continue
                    logger.info(f"New offer: {j.missionTitle}")
                    writer.write_one(j)
                    repository.insert(id)
        except Exception as e:
            logger.error(e)
            raise click.ClickException(f"Error during task execution : {str(e)}") from e

    logger.info("Starting ...")

    if continuous:
        logger.info(f"Set to wake up every {sleep_duration} seconds")
        while True:
            logger.info("Waking Up ...")
            task()
            logger.info("Going to sleep. Zzz")
            time.sleep(sleep_duration)
    else:
        task()
        logger.info("Done ...")


if __name__ == "__main__":
    cli()
