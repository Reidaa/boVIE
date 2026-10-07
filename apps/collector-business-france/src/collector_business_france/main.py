#!/usr/bin/env python3
"""
Bovie - A tool to discover VIE/VIA opportunities from Business France
"""

import hashlib
import json
import sys
from collections.abc import Callable

import click
from cli_common import EnvironmentCommand
from collector_store import record_page, seen
from loguru import logger
from mysql_common import make_engine
from mysql_common.env import load_env
from nats_client import Publisher
from offer_events import OfferDetails, OfferEvent
from pydantic import HttpUrl
from sqlalchemy.engine import Engine

from .config import configFromParams
from .display import display_fields
from .job import get_from_id, search_id
from .job.models.country import get_country_names
from .job.models.geozone import get_zone_names
from .job.models.job import Job
from .job.models.search import SearchParameters
from .job.models.specialization import get_specialization_names
from .t import Choice

DEFAULT_OFFER_LIMIT = 25


def normalize(job: Job) -> OfferEvent:
    return OfferEvent(
        type="discovered",
        source="business_france",
        source_offer_id=str(job.id),
        offer=OfferDetails(
            title=job.missionTitle[:256],
            organization=job.organizationName,
            country=job.countryName,
            city=job.cityName or job.cityAffectation,
            url=HttpUrl(f"https://mon-vie-via.businessfrance.fr/offres/{job.id}"),
            fields=display_fields(job),
        ),
    )


def task(
    params: SearchParameters,
    engine: Engine,
    publish: Callable[[OfferEvent], None],
    *,
    page_size: int = 25,
):
    scan = hashlib.sha256(
        json.dumps(params.model_dump(), sort_keys=True).encode()
    ).hexdigest()
    offset = 0
    # Replaying from zero is intentional: offset-based results can move between runs.
    while offset < params.limit:
        size = min(page_size, params.limit - offset)
        ids = search_id(params.model_copy(update={"skip": offset, "limit": size}))
        events = []
        for identity in ids:
            if seen(engine, str(identity)):
                continue
            job = get_from_id(identity)
            if job is None:
                raise RuntimeError(f"Unable to fetch offer {identity}")
            events.append(normalize(job))
        offset += len(ids)
        # Publish before recording: an unrecorded offer is published again next run.
        for event in events:
            publish(event)
        record_page(engine, events, [str(identity) for identity in ids], scan, offset)
        for event in events:
            logger.info(
                "New offer: {} in {} at {}",
                event.offer.title,
                event.offer.country,
                event.offer.organization,
            )
        if len(ids) < size:
            break


@click.command(cls=EnvironmentCommand)
@click.option(
    "--debug",
    default=False,
    type=click.BOOL,
    is_flag=True,
    help="Enable debug logging",
    envvar="BUSINESS_FRANCE_DEBUG",
)
@click.option(
    "--limit",
    default=DEFAULT_OFFER_LIMIT,
    type=click.IntRange(min=1),
    show_default=DEFAULT_OFFER_LIMIT,
    envvar="BUSINESS_FRANCE_LIMIT",
)
@click.option(
    "--geozone",
    "-g",
    multiple=True,
    envvar="BUSINESS_FRANCE_REGION",
    type=Choice(get_zone_names(), case_sensitive=False),
    help="Regions to filter on",
)
@click.option(
    "--country",
    "-c",
    multiple=True,
    envvar="BUSINESS_FRANCE_COUNTRY",
    type=Choice(get_country_names(), case_sensitive=False),
    help="Countries to filter on",
)
@click.option(
    "--specialization",
    "-s",
    multiple=True,
    envvar="BUSINESS_FRANCE_SPECIALIZATION",
    type=Choice(get_specialization_names(), case_sensitive=False),
    help="Specializations to filter on",
)
@click.version_option(
    package_name="bovie-collector-business-france", message="Bovie %(version)s"
)
def cli(
    debug: bool,
    limit: int,
    geozone: tuple[str],
    country: tuple[str],
    specialization: tuple[str],
):
    logger.remove()
    logger.add(sys.stdout, level="DEBUG" if debug else "INFO", diagnose=False)

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

    logger.info("Starting ...")
    engine = make_engine(load_env().database_url)
    try:
        with Publisher() as publisher:
            task(params=params, engine=engine, publish=publisher.publish)
    except Exception as e:
        logger.exception("Business France collection failed")
        raise click.ClickException("Business France collection failed") from e
    finally:
        engine.dispose()
    logger.info("Done ...")


if __name__ == "__main__":
    cli()
