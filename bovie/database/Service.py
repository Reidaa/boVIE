from bovie.database.Repository import OfferRepository


class DatabaseService:
    def __init__(self):
        self.offers = OfferRepository()
