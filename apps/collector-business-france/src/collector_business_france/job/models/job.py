from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

from collector_business_france.job.models.specialization import Specialization

BUSINESS_FRANCE_HOSTS = {
    "businessfrance.fr",
    "mon-vie-via.businessfrance.fr",
    "civiweb-api-prd.azurewebsites.net",
}


class Job(BaseModel):
    """The Business France offer fields that the collector reads.

    Pydantic ignores the other API fields, so their changes cannot fail a run.
    """

    activitySectorN1: str | None
    cityAffectation: str
    cityName: str | None
    contactEmail: str | None
    contactName: str | None
    countryName: str
    creationDate: str
    id: int
    indemnite: int | float
    missionDuration: int
    missionEndDate: str
    missionStartDate: str
    missionTitle: str
    organizationName: str
    specializations: list[Specialization] | None
    contactURL: str | None = None

    @property
    def external_application_url(self) -> str | None:
        if not self.contactURL:
            return None

        parsed_url = urlparse(self.contactURL)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            return None

        hostname = parsed_url.hostname.removeprefix("www.")
        if hostname in BUSINESS_FRANCE_HOSTS:
            return None

        return self.contactURL

    @field_validator("*", mode="after")
    @classmethod
    def strip(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("contactName", mode="after")
    @classmethod
    def sanitize(cls, v: str | None):
        if v is None:
            return "X"

        v = v.replace("Monsieur", "").replace("Madame", "").strip()

        if v == "":
            return "XXX"

        return v
