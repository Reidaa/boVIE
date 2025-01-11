from bovie.database.resources.OfferRepository import OfferRepository


class DatabaseService:
    def __init__(self):
        self.offers = OfferRepository()
