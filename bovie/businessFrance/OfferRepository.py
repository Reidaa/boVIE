from dataclasses import asdict, dataclass, field
from typing import List

import httpx

from bovie.businessFrance.IRepository import IRepository


@dataclass
class SearchParameters:
    activitySectorId: List[int] = field(default_factory=lambda: [])
    companiesSizes: List[str] = field(default_factory=lambda: [])
    countriesIds: List[int] = field(default_factory=lambda: [])
    entreprisesIds: List[int] = field(default_factory=lambda: [0])
    gerographicZones: List[int] = field(default_factory=lambda: [])
    missionsDurations: List[str] = field(default_factory=lambda: [])
    missionsTypesIds: List[str] = field(default_factory=lambda: [])
    specializationsIds: List[str] = field(default_factory=lambda: [])
    studiesLevelId: List[str] = field(default_factory=lambda: [])
    missionStartDate: str = None
    limit: int = 10
    query: str = ""
    skip: int = 0

    def dict(self):
        return asdict(self)


class OfferRepository(IRepository):
    def __init__(self):
        super().__init__()
        self.url = f"{self.url}/Offers"

    def search(self, params: SearchParameters):
        url = f"{self.url}/search"
        p = params.dict()
        r = httpx.post(url, json=p)

        return r.json()["result"]

    def findOne(self, offerID: int):
        url = f"{self.url}/details/{offerID}"
        r = httpx.get(url)

        return r.json()
