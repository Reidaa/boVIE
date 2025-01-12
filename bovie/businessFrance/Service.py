from typing import List

from bovie.businessFrance.resources.OfferService import (
    Offer,
    OfferService,
    SearchParameters,
)
from bovie.database.Service import DatabaseService

API_URL = "https://civiweb-api-prd.azurewebsites.net/api"


class Service:
    def __init__(self):
        self._offers_api = OfferService(api_url=API_URL)
        self._db = DatabaseService()

    def get_new_offers(self, params: SearchParameters) -> List[Offer]:
        new_offers: List[Offer] = []

        offers = self._offers_api.search(params)
        ids = [i.id for i in offers]
        existing_ids = self._db.offers.read()
        new_ids = [id for id in ids if id not in existing_ids]

        for id in new_ids:
            new_offers.append(self._offers_api.details(id))

        self._db.offers.insert_many(new_ids)

        return new_offers
