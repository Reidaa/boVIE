import json
import re
from functools import lru_cache

import httpx
from loguru import logger

from .models.job import Job
from .models.search import SearchParameters

URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
PUBLIC_OFFERS_URL = "https://mon-vie-via.businessfrance.fr/offres"
CLIENT = httpx.Client(base_url=URL, timeout=10)


@lru_cache(maxsize=1)
def public_api_key() -> str:
    response = CLIENT.get(PUBLIC_OFFERS_URL)
    response.raise_for_status()
    match = re.search(r'API_KEY:"((?:[^"\\]|\\.)*)"', response.text)
    if match is None:
        raise ValueError("Business France site no longer publishes an API key")
    return json.loads(f'"{match.group(1)}"')


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """Send with the public key; after a 401, fetch the key again and retry once.

    The site can rotate its key while a run is paging through results.
    """
    response = CLIENT.request(
        method, url, headers={"X-API-KEY": public_api_key()}, **kwargs
    )
    if response.status_code == httpx.codes.UNAUTHORIZED:
        logger.info("Refreshing the Business France API key")
        public_api_key.cache_clear()
        response = CLIENT.request(
            method, url, headers={"X-API-KEY": public_api_key()}, **kwargs
        )
    return response


def get_from_id(id: int) -> Job | None:
    url = f"/details/{id}"
    try:
        r = _request("GET", url)
        r.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to fetch Business France offer {}", id)
        raise

    job = Job.model_validate(r.json(), strict=True, by_alias=True)

    return job


def search_id(params: SearchParameters) -> list[int]:
    url = "/search"
    p = params.model_dump(by_alias=True)
    ids: list[int] = []

    logger.debug(f"Searching offers with parameters: {p}")

    try:
        r = _request("POST", url, json=p)
        r.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to search Business France offers")
        raise

    response_json = r.json()

    for result in response_json["result"]:
        ids.append(int(result["id"]))

    return ids
