from bovie.businessFrance.OfferRepository import OfferRepository


class BFClient:
    def __init__(self):
        self.offers = OfferRepository()
