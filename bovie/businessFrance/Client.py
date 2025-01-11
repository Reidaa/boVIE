from pathlib import Path
from typing import List

from bovie.businessFrance.OfferRepository import (
    Offer,
    OfferRepository,
    SearchParameters,
)


class Client:
    def __init__(self):
        self._offer_repository = OfferRepository()
        self._id_file = Path("ids.txt").absolute()

        try:
            open(self._id_file, "x")
        except FileExistsError:
            pass

    def _retrieve_existing_ids(self):
        with open(self._id_file, "r") as f:
            exising_ids = f.read().rstrip().lstrip().split("\n")

        return exising_ids

    def _write_new_ids(self, ids: List[int]):
        with open(self._id_file, "a") as f:
            for id in ids:
                f.write(f"{id}\n")

        return None

    def _get_new_ids(self, ids: List[int]) -> List[int]:
        existing_ids = self._retrieve_existing_ids()
        ids = [id for id in ids if str(id) not in existing_ids]

        return ids

    def get_new_offers(self, limit: int) -> List[Offer]:
        new_offers: List[Offer] = []
        params = SearchParameters(limit=limit)

        offers = self._offer_repository.search(params)
        ids = [i.id for i in offers]
        new_ids = self._get_new_ids(ids)

        self._write_new_ids(new_ids)

        for id in new_ids:
            new_offers.append(self._offer_repository.find_one(id))

        return new_offers
