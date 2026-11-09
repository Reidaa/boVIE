"""Board configuration and minimal projections of the Workday CXS API.

See docs/workday-api.md for the verified request contract.
"""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pydantic.alias_generators import to_camel


class WorkdayModel(BaseModel):
    # Workday and the board configuration use camelCase keys, as in the API body.
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)


class Board(WorkdayModel):
    """One company career site, e.g. https://example.wd1.myworkdayjobs.com/Careers.

    `search_text` and `applied_facets` are sent unchanged in the job list request;
    empty values collect every job on the board.
    """

    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    company: str = Field(min_length=1)
    search_text: str = ""
    applied_facets: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def workday_career_site(cls, url: HttpUrl) -> HttpUrl:
        labels = (url.host or "").split(".")
        if (
            url.scheme != "https"
            or len(labels) != 4
            or labels[2:] != ["myworkdayjobs", "com"]
            or not (url.path or "").strip("/")
        ):
            raise ValueError("Expected https://<tenant>.<wdN>.myworkdayjobs.com/<site>")
        return url

    @property
    def origin(self) -> str:
        return f"https://{self.url.host}"

    @property
    def tenant(self) -> str:
        return (self.url.host or "").split(".")[0]

    @property
    def site(self) -> str:
        # A locale may precede the site: /en-US/<site>.
        return (self.url.path or "").rstrip("/").rsplit("/", 1)[-1]

    @property
    def name(self) -> str:
        return f"{self.tenant}/{self.site}"

    @property
    def api_url(self) -> str:
        return f"{self.origin}/wday/cxs/{self.tenant}/{self.site}"


class Posting(WorkdayModel):
    title: str
    external_path: str

    @field_validator("external_path")
    @classmethod
    def job_path(cls, path: str) -> str:
        if not path.startswith("/job/") or ".." in path:
            raise ValueError("Unexpected Workday job path")
        return path

    @property
    def job_id(self) -> str:
        # Workday finds a job by this last segment; the location segment is ignored.
        return self.external_path.rsplit("/", 1)[-1]


class SearchResponse(WorkdayModel):
    # Set only on the first page; later pages return 0.
    total: int = Field(ge=0)
    job_postings: list[Posting]


class Country(WorkdayModel):
    alpha2_code: str | None = None


class RequisitionLocation(WorkdayModel):
    country: Country | None = None


class JobDetail(WorkdayModel):
    title: str
    job_posting_id: str
    posted: bool
    location: str | None = None
    additional_locations: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    time_type: str | None = None
    job_req_id: str | None = None
    job_requisition_location: RequisitionLocation | None = None


class DetailResponse(WorkdayModel):
    job_posting_info: JobDetail
