import httpx
from loguru import logger

from .models import Job, SearchParameters

URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
CLIENT = httpx.Client(base_url=URL)


def get_from_id(id: int) -> Job | None:
    url = f"/details/{id}"
    try:
        r = CLIENT.get(url)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch job -> {str(e)}")
        return None

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
    except Exception as e:
        logger.error(f"Failed to search offers -> {str(e)}")
        return []

    response_json = r.json()
    logger.debug(f"Search response: {response_json}")
    
    for result in response_json["result"]:
        logger.debug(f"Found offer: {result}")
        ids.append(Job.model_validate(result).id)
    # ids = [Job.model_validate(result).id for result in response_json["result"]]
    # logger.debug(f"Found offer IDs: {ids}")

    return ids
