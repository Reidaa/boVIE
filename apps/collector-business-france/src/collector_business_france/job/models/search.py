from pydantic import BaseModel, Field


class SearchParameters(BaseModel):
    activitySectorId: list[int] = Field(default_factory=lambda: [])
    companiesSizes: list[str] = Field(default_factory=lambda: [])
    countriesIds: list[str] = Field(default_factory=lambda: [])
    entreprisesIds: list[int] = Field(default_factory=lambda: [])
    gerographicZones: list[str] = Field(
        default_factory=lambda: [], alias="geographicZones"
    )  # Spelling mistake from the VIE API
    missionsDurations: list[str] = Field(default_factory=lambda: [])
    missionsTypesIds: list[str] = Field(default_factory=lambda: [])
    specializationsIds: list[str] = Field(default_factory=lambda: [])
    studiesLevelId: list[str] = Field(default_factory=lambda: [])
    missionStartDate: str | None = Field(default=None)
    limit: int = Field(default=10)
    query: str = Field(default="")
    skip: int = Field(default=0)
