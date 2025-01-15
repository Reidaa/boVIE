import logging
from typing import List, Optional

import httpx

from src.businessFrance.models import Offer, SearchParameters

logger = logging.getLogger("bovie.OfferService")


class OfferService:
    def __init__(self, api_url: str):
        self.url = f"{api_url}/Offers"

    def search(self, params: SearchParameters) -> List[int]:
        ids: List[Offer] = []
        url = f"{self.url}/search"
        p = params.dict()
        try:
            r = httpx.post(url, json=p)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to search offers: {str(e)}")
            return []

        ids = [result["id"] for result in r.json()["result"]]

        return ids

    def details(self, offer_id: int) -> Optional[Offer]:
        url = f"{self.url}/details/{offer_id}"
        try:
            r = httpx.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch offer: {str(e)}")
            return None

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
