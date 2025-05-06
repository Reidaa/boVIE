import httpx
from loguru import logger

from .enum import Regions, Specializations
from .model import Job, SearchParameters

DEFAULT_SEARCH_PARAMS = SearchParameters(
    limit=101,
    specializationsIds=[
        Specializations.INFORMATION_SYSTEMS.value,
        Specializations.SCIENTIFIC_AND_INDUSTRIAL_COMPUTING.value,
    ],
    geographicZones=[
        Regions.ASIA_PACIFIC.value,
        Regions.NORTH_AMERICA.value,
        Regions.SOUTH_AMERICA.value,
        Regions.WESTERN_EUROPE.value,
    ],
)

URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
CLIENT = httpx.Client(base_url=URL)


def get_by_id(id: int) -> Job | None:
    url = f"/details/{id}"
    try:
        r = CLIENT.get(url)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch job: {str(e)}")
        return None

    job = Job.model_validate(r.json(), strict=True, by_alias=True)

    return job


def search_id(params: SearchParameters) -> list[int]:
    url = f"/search"
    p = params.model_dump()
    try:
        r = CLIENT.post(url, json=p)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to search offers: {str(e)}")
        return []

    ids = [Job.model_validate(result).id for result in r.json()["result"]]

    return ids
