from dataclasses import asdict, dataclass, field
from typing import List

import httpx

from bovie.businessFrance.generated.models import Offer
from bovie.businessFrance.interfaces.IRepository import IRepository


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
        results: List[Offer] = []
        url = f"{self.url}/search"
        p = params.dict()
        r = httpx.post(url, json=p)

        if r.status_code != httpx.codes.OK:
            raise Exception()

        for r in r.json()["result"]:
            offer = Offer(
                id=r["id"],
                organizationName=r["organizationName"],
                missionTitle=r.get("missionTitle", ""),
                missionDuration=r.get("missionDuration", 0),
                viewCounter=r.get("viewCounter", 0),
                candidateCounter=r.get("candidateCounter", 0),
                missionType=r.get("missionType", ""),
                missionTypeEn=r.get("missionTypeEn", ""),
                organizationPresentation=r.get("organizationPresentation", ""),
                organizationUrlImage=r.get("organizationUrlImage", ""),
                organizationPathImage=r.get("organizationPathImage"),
                pathImage=r.get("pathImage"),
                activitySectorN1=r.get("activitySectorN1", ""),
                activitySectorN2=r.get("activitySectorN2"),
                activitySectorN3=r.get("activitySectorN3"),
                activitySectorN1Id=r.get("activitySectorN1Id", 0),
                ca=r.get("ca", ""),
                effectif=r.get("effectif", 0),
                organizationCountryCounter=r.get("organizationCountryCounter", ""),
                organizationExpertise=r.get("organizationExpertise"),
                cityAffectationId=r.get("cityAffectationId", 0),
                cityName=r.get("cityName", ""),
                cityNameEn=r.get("cityNameEn", ""),
                activitySectorOfferId=r.get("activitySectorOfferId", 0),
                levelStudyIds=r.get("levelStudyIds"),
                specializations=r.get("specializations"),
                missionDescription=r.get("missionDescription", ""),
                creationDate=r.get("creationDate", ""),
                missionStartDate=r.get("missionStartDate", ""),
                missionEndDate=r.get("missionEndDate", ""),
                startBroadcastDate=r.get("startBroadcastDate", ""),
                durationBroadcast=r.get("durationBroadcast", 0),
                organizationId=r.get("organizationId", 0),
                missionProfile=r.get("missionProfile", ""),
                countryId=r.get("countryId", ""),
                countryName=r.get("countryName", ""),
                countryNameEn=r.get("countryNameEn", ""),
                reference=r.get("reference", ""),
                contactName=r.get("contactName", ""),
                indemnite=r.get("indemnite", 0),
                idMotifDesactivationOffre=r.get("idMotifDesactivationOffre", 0),
                contactEmail=r.get("contactEmail", ""),
                cityAffectation=r.get("cityAffectation", ""),
                idNomenclatureSecteur=r.get("idNomenclatureSecteur"),
            )
            results.append(offer)

        return results

    def findOne(self, offerID: int) -> Offer:
        url = f"{self.url}/details/{offerID}"
        r = httpx.get(url)

        if r.status_code != httpx.codes.OK:
            raise Exception()

        response = r.json()
        offer = Offer(
            id=response["id"],
            organizationName=response["organizationName"],
            missionTitle=response.get("missionTitle", ""),
            missionDuration=response.get("missionDuration", 0),
            viewCounter=response.get("viewCounter", 0),
            candidateCounter=response.get("candidateCounter", 0),
            missionType=response.get("missionType", ""),
            missionTypeEn=response.get("missionTypeEn", ""),
            organizationPresentation=response.get("organizationPresentation", ""),
            organizationUrlImage=response.get("organizationUrlImage", ""),
            organizationPathImage=response.get("organizationPathImage"),
            pathImage=response.get("pathImage"),
            activitySectorN1=response.get("activitySectorN1", ""),
            activitySectorN2=response.get("activitySectorN2"),
            activitySectorN3=response.get("activitySectorN3"),
            activitySectorN1Id=response.get("activitySectorN1Id", 0),
            ca=response.get("ca", ""),
            effectif=response.get("effectif", 0),
            organizationCountryCounter=response.get("organizationCountryCounter", ""),
            organizationExpertise=response.get("organizationExpertise"),
            cityAffectationId=response.get("cityAffectationId", 0),
            cityName=response.get("cityName", ""),
            cityNameEn=response.get("cityNameEn", ""),
            activitySectorOfferId=response.get("activitySectorOfferId", 0),
            levelStudyIds=response.get("levelStudyIds"),
            specializations=response.get("specializations"),
            missionDescription=response.get("missionDescription", ""),
            creationDate=response.get("creationDate", ""),
            missionStartDate=response.get("missionStartDate", ""),
            missionEndDate=response.get("missionEndDate", ""),
            startBroadcastDate=response.get("startBroadcastDate", ""),
            durationBroadcast=response.get("durationBroadcast", 0),
            organizationId=response.get("organizationId", 0),
            missionProfile=response.get("missionProfile", ""),
            countryId=response.get("countryId", ""),
            countryName=response.get("countryName", ""),
            countryNameEn=response.get("countryNameEn", ""),
            reference=response.get("reference", ""),
            contactName=response.get("contactName", ""),
            indemnite=response.get("indemnite", 0),
            idMotifDesactivationOffre=response.get("idMotifDesactivationOffre", 0),
            contactEmail=response.get("contactEmail", ""),
            cityAffectation=response.get("cityAffectation", ""),
            idNomenclatureSecteur=response.get("idNomenclatureSecteur"),
        )

        return offer
