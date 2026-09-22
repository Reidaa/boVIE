import httpx
from loguru import logger

from .models.job import Job
from .models.search import SearchParameters

URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
CLIENT = httpx.Client(base_url=URL, timeout=10)


def get_from_id(id: int) -> Job | None:
    url = f"/details/{id}"
    try:
        r = CLIENT.get(url)
        r.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to fetch Business France offer {}", id)
        raise

    job = Job.model_validate(r.json(), strict=True, by_alias=True)

    return job


def search_id(params: SearchParameters) -> list[int]:
    url = "/search"
    p = params.model_dump()
    ids: list[int] = []

    logger.debug(f"Searching offers with parameters: {p}")

    try:
        r = CLIENT.post(url, json=p)
        r.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to search Business France offers")
        raise

    response_json = r.json()

    for result in response_json["result"]:
        ids.append(int(result["id"]))

    return ids
