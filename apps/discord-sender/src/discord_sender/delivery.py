"""Render and send queued Discord messages."""

import time

import httpx
from discord_store import Delivery
from loguru import logger
from mysql_common.queue import claim, finish, retry_later
from offer_events import OfferEvent
from sqlalchemy.engine import Engine


def discord_payload(event: OfferEvent) -> dict:
    offer = event.offer
    fields = [field.model_dump() for field in offer.fields]
    if not fields:
        fields = [
            {"name": "Entreprise", "value": offer.organization[:1024] or "N/A"},
            {"name": "Lieu", "value": f"{offer.city}, {offer.country}"[:1024]},
        ]
    # Discord's aggregate embed text limit is 6000 characters.
    remaining = 6000 - len(offer.title)
    bounded = []
    for field in fields:
        available = remaining - len(field["name"])
        if available <= 0:
            break
        field["value"] = field["value"][:available]
        remaining -= len(field["name"]) + len(field["value"])
        bounded.append(field)
    return {
        "username": "boVIE",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": offer.title,
                "url": str(offer.url),
                "color": 341401,
                "fields": bounded,
            }
        ],
    }


def deliver_one(engine: Engine, client: httpx.Client, webhook: str) -> bool:
    work = claim(engine, Delivery)
    if work is None:
        return False
    try:
        # wait=true makes Discord confirm the message was saved before it answers.
        response = client.post(
            webhook,
            params={"wait": "true"},
            json=discord_payload(
                OfferEvent.model_validate(work.payload),
            ),
        )
    except Exception:
        retry_later(engine, Delivery, work)
        raise
    if response.status_code == 429:
        # Wait as long as Discord asks; sending sooner only extends the limit.
        wait = float(response.headers.get("Retry-After", 1))
        retry_later(engine, Delivery, work, delay_seconds=wait)
        logger.warning("Discord answered HTTP 429; waiting {} s", wait)
        time.sleep(wait)
        return True
    if not response.is_success:
        # Log only the status: the exception message contains the webhook URL.
        logger.warning("Discord answered HTTP {}", response.status_code)
        retry_later(engine, Delivery, work)
        response.raise_for_status()
    if not finish(engine, Delivery, work):
        logger.warning(
            "Delivery {} was sent after its lease expired; Discord may show it twice",
            work.event_id,
        )
    return True
