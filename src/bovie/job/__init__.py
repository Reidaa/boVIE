import json
import os
import re

import httpx
from dotenv import load_dotenv
from loguru import logger

from .models.job import Job
from .models.search import SearchParameters

load_dotenv()

URL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
FRONTEND_URL = "https://mon-vie-via.businessfrance.fr/offres/recherche"
API_KEY_PATTERN = re.compile(r'API_KEY\s*:\s*("(?:\\.|[^"\\])*")')


def _create_client() -> httpx.Client:
    api_key = os.getenv("BOVIE_API_KEY")
    headers = {"X-API-KEY": api_key} if api_key else {}
    return httpx.Client(base_url=URL, headers=headers, timeout=10)


CLIENT = _create_client()


def _fetch_api_key() -> str:
    response = CLIENT.get(FRONTEND_URL)
    response.raise_for_status()

    match = API_KEY_PATTERN.search(response.text)
    if not match:
        raise RuntimeError("Civiweb API key was not found")

    return json.loads(match.group(1))


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    response = CLIENT.request(method, url, **kwargs)
    if response.status_code == httpx.codes.UNAUTHORIZED:
        logger.info("Refreshing Civiweb API key")
        CLIENT.headers["X-API-KEY"] = _fetch_api_key()
        response = CLIENT.request(method, url, **kwargs)
    return response


def get_from_id(id: int) -> Job | None:
    url = f"/details/{id}"
    try:
        r = _request("GET", url)
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
        r = _request("POST", url, json=p)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to search offers -> {str(e)}")
        return []

    response_json = r.json()

    for result in response_json["result"]:
        ids.append(Job.model_validate(result).id)

    return ids
