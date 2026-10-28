"""Workday collector: one run scans every configured company board."""

import hashlib
import json
import time
from collections.abc import Callable, Sequence

import click
import httpx
from cli_common import EnvironmentCommand, configure_logging
from collector_store import SourceSilent, record_page, require_recent_results, seen
from loguru import logger
from mysql_common import make_engine
from mysql_common.env import load_env
from nats_client import Publisher
from offer_events import DisplayField, OfferDetails, OfferEvent
from pydantic import HttpUrl, TypeAdapter
from sqlalchemy.engine import Engine

from collector_workday.api import Board, DetailResponse, JobDetail, SearchResponse

# Workday rejects a larger page with 400.
PAGE_SIZE = 20


class CollectionFailed(RuntimeError):
    """At least one board failed; the others were still collected."""


def load_boards(text: str) -> list[Board]:
    """Parse the JSON list of boards from WORKDAY_BOARDS; it must not be empty."""
    boards = TypeAdapter(list[Board]).validate_json(text) if text.strip() else []
    if not boards:
        raise ValueError("WORKDAY_BOARDS must be a JSON list of at least one board")
    return boards


def normalize(board: Board, external_path: str, job: JobDetail) -> OfferEvent:
    fields = [
        DisplayField(name="Entreprise", value=board.company[:1024]),
        DisplayField(
            name="Lieu",
            value=", ".join(filter(None, [job.location, *job.additional_locations]))[
                :1024
            ]
            or "N/A",
        ),
    ]
    for name, value in (
        ("Publié le", job.start_date),
        ("Contrat", job.time_type),
        ("Date limite", job.end_date),
        ("Référence", job.job_req_id),
    ):
        if value:
            fields.append(DisplayField(name=name, value=value[:1024]))
    location = job.job_requisition_location
    country = location.country.alpha2_code if location and location.country else None
    return OfferEvent(
        type="discovered",
        source="workday",
        source_offer_id=f"{board.name}/{job.job_posting_id}",
        offer=OfferDetails(
            title=job.title.strip()[:256],
            organization=board.company,
            country=country or "N/A",
            city=job.location or "N/A",
            url=HttpUrl(f"{board.origin}/{board.site}{external_path}"),
            fields=fields,
        ),
    )


def collect_board(
    engine: Engine,
    client: httpx.Client,
    publish: Callable[[OfferEvent], None],
    board: Board,
    *,
    limit: int,
    delay: float,
):
    scan = hashlib.sha256(
        json.dumps(
            [board.api_url, board.search_text, board.applied_facets, limit],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    inspected = offset = 0
    total = None
    # Restart at offset 0 each run: the newest postings come first.
    while inspected < limit:
        time.sleep(delay)
        response = client.post(
            f"{board.api_url}/jobs",
            json={
                "limit": PAGE_SIZE,
                "offset": offset,
                "searchText": board.search_text,
                "appliedFacets": board.applied_facets,
            },
        )
        response.raise_for_status()
        result = SearchResponse.model_validate(response.json())
        if total is None:
            total = result.total
        postings = result.job_postings[: limit - inspected]
        inspected += len(postings)
        events = []
        for posting in postings:
            if seen(engine, f"{board.name}/{posting.job_id}"):
                continue
            time.sleep(delay)
            response = client.get(f"{board.api_url}{posting.external_path}")
            if response.status_code in (httpx.codes.NOT_FOUND, httpx.codes.GONE):
                # The job was removed after the list showed it.
                logger.warning("Workday job {} is gone; skipping it", posting.job_id)
                continue
            response.raise_for_status()
            job = DetailResponse.model_validate(response.json()).job_posting_info
            if job.job_posting_id != posting.job_id:
                raise ValueError("Workday detail identity does not match its posting")
            if not job.posted:
                continue
            events.append(normalize(board, posting.external_path, job))
        # Publish before recording: an unrecorded offer is published again next run.
        for event in events:
            publish(event)
        record_page(
            engine,
            events,
            [f"{board.name}/{posting.job_id}" for posting in postings],
            scan,
            offset,
        )
        for event in events:
            logger.info(
                "New Workday offer: {} at {}",
                event.offer.title,
                event.offer.organization,
            )
        offset += len(result.job_postings)
        # Workday serves the first page again past the end, so stop at `total`.
        if len(result.job_postings) < PAGE_SIZE or offset >= total:
            break
    require_recent_results(engine, scan)


def collect(
    engine: Engine,
    client: httpx.Client,
    publish: Callable[[OfferEvent], None],
    boards: Sequence[Board],
    *,
    limit: int = 40,
    delay: float = 1.0,
):
    """Collect every board, then raise CollectionFailed if any of them failed.

    A board fails alone on HTTP, response-shape or silent-source errors. Broker and
    database errors affect every board, so they stop the run at once.
    """
    failed = []
    for board in boards:
        try:
            collect_board(engine, client, publish, board, limit=limit, delay=delay)
        except httpx.HTTPError, ValueError, SourceSilent:
            logger.exception("Workday board {} failed", board.name)
            failed.append(board.name)
    if failed:
        raise CollectionFailed(f"Workday boards failed: {', '.join(failed)}")


@click.command(cls=EnvironmentCommand)
@click.option(
    "--boards",
    "boards_json",
    default="",
    envvar="WORKDAY_BOARDS",
    help="Required JSON list of boards to collect.",
)
@click.option(
    "--limit",
    default=40,
    type=click.IntRange(min=1),
    envvar="WORKDAY_LIMIT",
    help="Maximum job postings to inspect per board.",
)
def main(boards_json: str, limit: int):
    """Discover new jobs on the configured Workday career sites."""
    configure_logging()
    # Fail on configuration before connecting to MySQL or NATS.
    try:
        boards = load_boards(boards_json)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="WORKDAY_BOARDS") from error
    engine = make_engine(load_env().database_url)
    try:
        with (
            httpx.Client(timeout=15, headers={"Accept": "application/json"}) as client,
            Publisher() as publisher,
        ):
            collect(engine, client, publisher.publish, boards, limit=limit)
    except Exception as error:
        logger.exception("Workday collection failed")
        raise click.ClickException(
            "Workday collection failed; retry will replay discovery"
        ) from error
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
