from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class SearchParameters(BaseModel):
    """The body of a Business France search request.

    `model_dump(by_alias=True)` gives the camelCase keys that the API expects.
    """

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)

    activity_sector_id: list[int] = Field(default_factory=list)
    companies_sizes: list[str] = Field(default_factory=list)
    countries_ids: list[str] = Field(default_factory=list)
    entreprises_ids: list[int] = Field(default_factory=list)
    geographic_zones: list[str] = Field(default_factory=list)
    missions_durations: list[str] = Field(default_factory=list)
    missions_types_ids: list[str] = Field(default_factory=list)
    specializations_ids: list[str] = Field(default_factory=list)
    studies_level_id: list[str] = Field(default_factory=list)
    mission_start_date: str | None = Field(default=None)
    limit: int = Field(default=10)
    query: str = Field(default="")
    skip: int = Field(default=0)
