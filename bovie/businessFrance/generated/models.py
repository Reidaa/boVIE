from dataclasses import dataclass
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
