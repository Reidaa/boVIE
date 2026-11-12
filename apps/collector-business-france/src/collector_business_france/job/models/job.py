from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

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

    # The API uses camelCase keys; the fields are snake_case.
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)

    activity_sector_n1: str | None
    city_affectation: str
    city_name: str | None
    contact_email: str | None
    contact_name: str | None
    country_name: str
    creation_date: str
    id: int
    indemnite: int | float
    mission_duration: int
    mission_end_date: str
    mission_start_date: str
    mission_title: str
    organization_name: str
    specializations: list[Specialization] | None
    contact_url: str | None = Field(default=None, alias="contactURL")

    @property
    def external_application_url(self) -> str | None:
        if not self.contact_url:
            return None

        parsed_url = urlparse(self.contact_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            return None

        hostname = parsed_url.hostname.removeprefix("www.")
        if hostname in BUSINESS_FRANCE_HOSTS:
            return None

        return self.contact_url

    @field_validator("*", mode="after")
    @classmethod
    def strip(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("contact_name", mode="after")
    @classmethod
    def sanitize(cls, v: str | None):
        if v is None:
            return "X"

        v = v.replace("Monsieur", "").replace("Madame", "").strip()

        if v == "":
            return "XXX"

        return v
