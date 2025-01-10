BASE_ENDPOINT = ""

SEARCH_ENDPOINT = "/Offers/search"

COMPANY_ENDPOINT = "/Companies/details/{CompanyID}"

OFFER_ENDPOINT = "Offers/details/{OfferID}"


class IRepository:
    def __init__(self):
        self.url = "https://civiweb-api-prd.azurewebsites.net/api"


class CompanyRepository(IRepository):
    def __init__(self):
        self.url = "{self.url}/Companies"
