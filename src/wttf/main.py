import hashlib
import json
import sys
from urllib.parse import quote

import click
import httpx
from loguru import logger
from pydantic import HttpUrl
from sqlalchemy.engine import Engine

from bovie.collector import record_page, seen
from bovie.db import make_engine
from bovie.env import EnvironmentCommand, load_env
from bovie.events import DisplayField, OfferDetails, OfferDiscovered
from wttf.core.search import DetailResponse, JobDetail, SearchResponse

API_URL = "https://api.welcometothejungle.com"


def normalize(job: JobDetail) -> OfferDiscovered:
    fields = [
        DisplayField(name="Entreprise", value=job.organization.name[:1024]),
        DisplayField(
            name="Lieu",
            value=", ".join(
                f"{office.city} ({office.country_code})" for office in job.offices
            )[:1024]
            or "N/A",
        ),
        DisplayField(name="Publié le", value=job.published_at[:1024]),
        DisplayField(name="Contrat", value=job.contract_type),
    ]
    if job.salary_min is not None or job.salary_max is not None:
        fields.append(
            DisplayField(
                name="Salaire",
                value=(
                    f"{job.salary_min or '?'} – {job.salary_max or '?'} "
                    f"{job.salary_currency or ''} / {job.salary_period or 'N/A'}"
                ),
            )
        )
    if job.start_date:
        fields.append(DisplayField(name="Début", value=job.start_date[:1024]))
    if job.apply_url and job.apply_url.startswith(("https://", "http://")):
        fields.append(DisplayField(name="Candidature", value=job.apply_url[:1024]))
    office = job.offices[0] if job.offices else None
    return OfferDiscovered(
        source="wttj",
        source_offer_id=job.wttj_reference,
        offer=OfferDetails(
            title=job.name.strip()[:256],
            organization=job.organization.name,
            country=office.country_code if office else "N/A",
            city=office.city if office else "N/A",
            url=HttpUrl(
                f"https://www.welcometothejungle.com/fr/companies/"
                f"{quote(job.organization.slug, safe='')}/jobs/{quote(job.slug, safe='')}"
            ),
            fields=fields,
        ),
    )


def collect(
    engine: Engine,
    client: httpx.Client,
    *,
    query: str = "VIE",
    limit: int = 50,
    max_pages: int = 5,
    countries: tuple[str, ...] = (),
):
    scan = hashlib.sha256(
        json.dumps([query, countries, limit, max_pages]).encode()
    ).hexdigest()
    inspected = 0
    # Restart at page 1 because ranked search results can move between invocations.
    for page in range(1, max_pages + 1):
        response = client.get(
            "/api/v3/public/jobs", params={"job_title": query, "page": page}
        )
        response.raise_for_status()
        result = SearchResponse.model_validate(response.json())
        if result.metadata.page != page:
            raise ValueError("WTTJ returned an unexpected page number")
        events = []
        for hit in result.data[: limit - inspected]:
            inspected += 1
            if hit.contract_type != "vie" or seen(engine, hit.reference):
                continue
            response = client.get(
                f"/api/v3/organizations/{quote(hit.organization.slug, safe='')}/jobs/{quote(hit.slug, safe='')}"
            )
            response.raise_for_status()
            job = DetailResponse.model_validate(response.json()).job
            if job.wttj_reference != hit.reference:
                raise ValueError(
                    "WTTJ detail identity does not match its search result"
                )
            if job.contract_type != "vie" or job.status != "published":
                continue
            if countries and not any(
                office.country_code in countries for office in job.offices
            ):
                continue
            events.append(normalize(job))
        for event in record_page(engine, events, scan, page):
            logger.info(
                "New WTTJ offer: {} at {}", event.offer.title, event.offer.organization
            )
        if inspected >= limit or not result.data or page >= result.metadata.page_count:
            break


@click.command(cls=EnvironmentCommand)
@click.option("--query", default="VIE", envvar="WTTJ_QUERY", show_default=True)
@click.option(
    "--limit",
    default=50,
    type=click.IntRange(min=1),
    envvar="WTTJ_LIMIT",
    help="Maximum search results to inspect.",
)
@click.option(
    "--max-pages", default=5, type=click.IntRange(min=1), envvar="WTTJ_MAX_PAGES"
)
@click.option(
    "--country", "countries", multiple=True, help="ISO country code, e.g. CA."
)
def main(query: str, limit: int, max_pages: int, countries: tuple[str, ...]):
    """Discover VIE offers on Welcome to the Jungle using its public search."""
    logger.remove()
    logger.add(sys.stderr, diagnose=False)
    engine = make_engine(load_env().database_url)
    try:
        with httpx.Client(base_url=API_URL, timeout=15) as client:
            collect(
                engine,
                client,
                query=query,
                limit=limit,
                max_pages=max_pages,
                countries=tuple(country.upper() for country in countries),
            )
    except Exception as error:
        logger.exception("WTTJ collection failed")
        raise click.ClickException(
            "WTTJ collection failed; retry will replay discovery"
        ) from error
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
