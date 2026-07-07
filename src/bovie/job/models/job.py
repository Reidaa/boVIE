from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from bovie.job.models.specialization import Specialization

BUSINESS_FRANCE_HOSTS = {
    "businessfrance.fr",
    "www.businessfrance.fr",
    "mon-vie-via.businessfrance.fr",
    "civiweb-api-prd.azurewebsites.net",
}


class Job(BaseModel):
    activitySectorN1: str | None
    activitySectorN1Id: int
    activitySectorN2: str | None
    activitySectorN3: str | None
    activitySectorOfferId: int
    ca: str | None
    candidateCounter: int
    cityAffectation: str
    cityAffectationId: int
    cityName: str | None
    cityNameEn: str
    contactEmail: str | None
    contactName: str | None
    countryId: str
    countryName: str
    countryNameEn: str
    creationDate: str
    durationBroadcast: int | float
    effectif: int
    id: int
    idMotifDesactivationOffre: int
    idNomenclatureSecteur: str | None
    indemnite: int | float
    levelStudyIds: str | None
    missionDescription: str | None = Field(repr=False)
    missionDuration: int
    missionEndDate: str
    missionProfile: str | None
    missionStartDate: str
    missionTitle: str
    missionType: str
    missionTypeEn: str
    organizationCountryCounter: str | None
    organizationExpertise: str | None
    organizationId: int
    organizationName: str
    organizationPathImage: str | None
    organizationPresentation: str | None
    organizationUrlImage: str | None
    pathImage: str | None
    reference: str | None
    specializations: list[Specialization] | None
    startBroadcastDate: str
    viewCounter: int
    externalJobId: str | None
    contactURL: str | None = None
    dateCandidature: str | None

    @property
    def external_application_url(self) -> str | None:
        if not self.contactURL:
            return None

        parsed_url = urlparse(self.contactURL)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            return None

        hostname = parsed_url.hostname.removeprefix("www.")
        business_france_hosts = {
            host.removeprefix("www.") for host in BUSINESS_FRANCE_HOSTS
        }
        if hostname in business_france_hosts:
            return None

        return self.contactURL

    @property
    def has_external_application(self) -> bool:
        return self.external_application_url is not None

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
