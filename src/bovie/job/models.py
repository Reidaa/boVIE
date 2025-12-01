from pydantic import BaseModel, Field, field_validator


class specialization(BaseModel):
    specializationId: int
    specializationLabel: str
    specializationLabelEn: str
    specializationParentId: int


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
    specializations: list[specialization] | None
    startBroadcastDate: str
    viewCounter: int
    externalJobId: str | None
    dateCandidature: str | None

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
