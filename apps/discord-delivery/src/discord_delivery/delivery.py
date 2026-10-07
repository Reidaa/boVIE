"""Render and send pending Discord notifications."""

import httpx
from job_contracts import OfferDiscovered
from job_database.queue import claim, finish, retry_later
from notification_store import Delivery
from sqlalchemy.engine import Engine


def discord_payload(event: OfferDiscovered) -> dict:
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
        response = client.post(
            webhook,
            json=discord_payload(
                OfferDiscovered.model_validate(work.payload),
            ),
        )
        response.raise_for_status()
    except Exception:
        retry_later(engine, Delivery, work)
        raise
    finish(engine, Delivery, work)
    return True
