from pydantic import BaseModel, Field


class SearchParameters(BaseModel):
    activitySectorId: list[int] = Field(default_factory=list)
    companiesSizes: list[str] = Field(default_factory=list)
    countriesIds: list[str] = Field(default_factory=list)
    entreprisesIds: list[int] = Field(default_factory=list)
    gerographicZones: list[str] = Field(
        default_factory=list, alias="geographicZones"
    )  # Spelling mistake from the VIE API
    missionsDurations: list[str] = Field(default_factory=list)
    missionsTypesIds: list[str] = Field(default_factory=list)
    specializationsIds: list[str] = Field(default_factory=list)
    studiesLevelId: list[str] = Field(default_factory=list)
    missionStartDate: str | None = Field(default=None)
    limit: int = Field(default=10)
    query: str = Field(default="")
    skip: int = Field(default=0)
