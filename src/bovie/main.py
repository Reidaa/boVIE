#!/usr/bin/env python3
"""
Bovie - A tool to discover VIE/VIA opportunities from Business France
"""

import sys

import click
from dotenv import load_dotenv
from loguru import logger

from .config import configFromParams
from .db import JobOffer
from .job import get_from_id, search_id
from .job.model import SearchParameters
from .job.models.country import get_country_names
from .job.models.geozone import get_zone_names
from .job.models.specialization import get_specialization_names
from .job.writer import DiscordWriter, JobWriter, TerminalWriter
from .t import Choice

load_dotenv(override=True)

logger.remove()


DEFAULT_BOVIE_OFFER_MAX = 25
DEFAULT_BOVIE_CONTINUOUS = False
DEFAULT_BOVIE_SLEEP_DURATION = 60
DEFAULT_DISCORD_WEBHOOK_URL = ""


def task(params: SearchParameters, writers: list[JobWriter] | None = None):
    if writers is None:
        writers = [TerminalWriter()]

    ids = search_id(params)
    logger.debug(f"Found {len(ids)} offers")

    if not ids:
        logger.info("No offers found")
        return

    logger.debug(f"Ids: {ids}")
    for id in ids:
        if id in JobOffer.all():
            continue
        j = get_from_id(id)
        if not j:
            logger.warning(f"Failed to fetch offer ID {id}")
            continue
        for writer in writers:
            logger.debug(f"Writing offer ID {id} using {writer.__class__.__name__}")
            writer.write_one(j)
            JobOffer.create(id)


@click.command()
@click.option(
    "--debug",
    default=False,
    type=click.BOOL,
    is_flag=True,
    help="Enable debug logging",
    envvar="BOVIE_DEBUG",
)
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
    envvar="BOVIE_LIMIT",
)
@click.option(
    "--geozone",
    "-g",
    multiple=True,
    envvar="BOVIE_REGION",
    type=Choice(get_zone_names(), case_sensitive=False),
    help="Regions to filter on",
)
@click.option(
    "--country",
    "-c",
    multiple=True,
    envvar="BOVIE_COUNTRY",
    type=Choice(get_country_names(), case_sensitive=False),
    help="Countries to filter on",
)
@click.option(
    "--specialization",
    "-s",
    multiple=True,
    envvar="BOVIE_SPECIALIZATION",
    type=Choice(get_specialization_names(), case_sensitive=False),
    help="Specializations to filter on",
)
@click.version_option(message="Bovie %(version)s")
def cli(
    debug: bool,
    webhook_url: str,
    limit: int,
    geozone: tuple[str],
    country: tuple[str],
    specialization: tuple[str],
):
    if debug:
        logger.add(sys.stdout, level="DEBUG")
    else:
        logger.add(sys.stdout, level="INFO")

    config = configFromParams(
        limit=limit,
        regions=geozone,
        specializations=specialization,
        countries=country,
    )
    params: SearchParameters = SearchParameters(
        limit=config.search.limit,
        specializationsIds=list(config.search.specializations),
        geographicZones=list(config.search.regions),
        countriesIds=list(config.search.countries),
    )

    logger.debug(f"limit: {limit}")
    logger.debug(f"geozones: {geozone}")
    logger.debug(f"specializations: {specialization}")
    logger.debug(f"countries: {country}")
    logger.debug(f"Config: {config}")

    logger.debug(f"Webhook URL: {webhook_url}")

    writers: list[JobWriter] = [
        TerminalWriter(),
    ]

    if webhook_url:
        writers.append(DiscordWriter(webhook_url=webhook_url))

    logger.debug(f"Writers: {writers}")

    logger.info("Starting ...")
    try:
        task(params=params, writers=writers)
    except Exception as e:
        error = f"Error during task execution -> {str(e)}"
        logger.error(error)
        raise click.ClickException(error) from e
    logger.info("Done ...")


if __name__ == "__main__":
    cli()
