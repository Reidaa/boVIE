from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class StudyLevel:
    studyLevelId: int
    studyLevelName: str
    studyLevelNameEn: str
    studyLevelOrder: str


@dataclass
class MissionType:
    missionTypeId: int
    missionTypeLabel: str
    missionTypeLabelEn: str


@dataclass
class EntrepriseType:
    entrepriseTypeId: int
    typeEntreprise: str
    typeEntrepriseEn: str


@dataclass
class ActivitySector:
    sectorId: int
    parentSectorId: int
    label: str
    ordre: int
    level: int
    originalSectorId: int
    isSectorN1: bool
    codeGED: Optional[str]


@dataclass
class Specialization:
    specializationId: int
    specializationCode: str
    specializationLabel: str
    specializationLabelEn: str
    specializationParentId: int


@dataclass
class Dataset:
    studyLevels: List[StudyLevel]
    missionTypes: List[MissionType]
    entrepriseTypes: List[EntrepriseType]
    activitySectors: List[ActivitySector]
    specializations: List[Specialization]


@dataclass
class GeographicZone:
    geographicZoneId: int
    geographicZoneLabel: str
    geographicZoneLabelEn: str


@dataclass
class GeographicZonesDataset:
    result: List[GeographicZone]
    count: int
    fileShareUrl: Optional[str]
    logosContainer: Optional[str]
    fileShareSasToken: Optional[str]


@dataclass
class Offer:
    activitySectorN1: str
    activitySectorN1Id: int
    activitySectorN2: Optional[str]
    activitySectorN3: Optional[str]
    activitySectorOfferId: int
    ca: Optional[str]
    candidateCounter: int
    cityAffectation: str
    cityAffectationId: int
    cityName: Optional[str]
    cityNameEn: str
    contactEmail: Optional[str]
    contactName: Optional[str]
    countryId: str
    countryName: str
    countryNameEn: str
    creationDate: str
    durationBroadcast: int
    effectif: int
    id: int
    idMotifDesactivationOffre: int
    idNomenclatureSecteur: Optional[str]
    indemnite: int
    levelStudyIds: Optional[str]
    missionDescription: str
    missionDuration: int
    missionEndDate: str
    missionProfile: Optional[str]
    missionStartDate: str
    missionTitle: str
    missionType: str
    missionTypeEn: str
    organizationCountryCounter: str
    organizationExpertise: Optional[str]
    organizationId: int
    organizationName: str
    organizationPathImage: Optional[str]
    organizationPresentation: Optional[str]
    organizationUrlImage: str
    pathImage: Optional[str]
    reference: Optional[str]
    specializations: Optional[str]
    startBroadcastDate: str
    viewCounter: int
    externalJobId: Optional[str] = ""
    dateCandidature: Optional[str] = ""


@dataclass
class SearchDataset:
    results: List[Offer]


@dataclass
class SearchParameters:
    activitySectorId: List[int] = field(default_factory=lambda: [])
    companiesSizes: List[str] = field(default_factory=lambda: [])
    countriesIds: List[int] = field(default_factory=lambda: [])
    entreprisesIds: List[int] = field(default_factory=lambda: [])
    gerographicZones: List[str] = field(default_factory=lambda: [])
    missionsDurations: List[str] = field(default_factory=lambda: [])
    missionsTypesIds: List[str] = field(default_factory=lambda: [])
    specializationsIds: List[str] = field(default_factory=lambda: [])
    studiesLevelId: List[str] = field(default_factory=lambda: [])
    missionStartDate: str = None
    limit: int = 10
    query: str = ""
    skip: int = 0

    def dict(self):
        return asdict(self)
