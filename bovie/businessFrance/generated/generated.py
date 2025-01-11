from bovie.businessFrance.generated.models import (
    ActivitySector,
    Dataset,
    EntrepriseType,
    GeographicZone,
    GeographicZonesDataset,
    MissionType,
    Specialization,
    StudyLevel,
)

searchParameters = Dataset(
    studyLevels=[
        StudyLevel(
            6,
            "< Bac                                             ",
            "< High School Diploma",
            "1",
        ),
        StudyLevel(
            1,
            "Bac                                               ",
            "High School Diploma",
            "2",
        ),
        StudyLevel(7, "bac+1", "1 year of higher education - ECTS : 60", "3"),
        StudyLevel(2, "bac+2", "2 years of higher education - ECTS : 120", "4"),
        StudyLevel(
            8, "bac+3", "3 years of higher education - ECTS : 180 (Bachelor)", "5"
        ),
        StudyLevel(3, "bac+4", "4 years of higher education - ECTS : 240", "6"),
        StudyLevel(
            4,
            "bac+5 et plus",
            "5 years of higher education or more - ECTS : 300 (Master)",
            "7",
        ),
    ],
    missionTypes=[MissionType(1, "VIE", "VIE"), MissionType(3, "VIA", "VIA")],
    entrepriseTypes=[
        EntrepriseType(1, "Start-up", "Startup"),
        EntrepriseType(2, "PME/ETI", "SME - mid-size company"),
        EntrepriseType(3, "Grandes entreprises", "Large company"),
        EntrepriseType(4, "Organisme public", "Public administration"),
    ],
    activitySectors=[
        ActivitySector(100001, 0, "AGROALIMENTAIRE", 1, 1, 1, False, None),
        ActivitySector(100002, 0, "BEAUTE, ESTHETIQUE", 2, 1, 2, False, None),
        ActivitySector(
            100003, 0, "MODE, TEXTILE, UNIVERS DE L'ENFANT", 3, 1, 3, False, None
        ),
        ActivitySector(
            100004,
            0,
            "ACTIVITES\u00a0DE COMMERCE (de gros et détail)",
            4,
            1,
            4,
            False,
            None,
        ),
        ActivitySector(
            100005, 0, "DECORATION, AMENAGEMENT ET DESIGN", 5, 1, 5, False, None
        ),
        ActivitySector(100006, 0, "ENERGIES", 6, 1, 6, False, None),
        ActivitySector(100007, 0, "ENVIRONNEMENT", 7, 1, 7, False, None),
        ActivitySector(
            100008, 0, "INDUSTRIES CHIMIQUES ET PLASTURGIE", 8, 1, 8, False, None
        ),
        ActivitySector(100009, 0, "SANTE", 9, 1, 9, False, None),
        ActivitySector(
            100010, 0, "EMBALLAGE ET CONDITIONNEMENT", 10, 1, 10, False, None
        ),
        ActivitySector(
            100011,
            0,
            "TECHNOLOGIES DE L'INFORMATION ET DES TELECOMMUNICATIONS",
            11,
            1,
            11,
            False,
            None,
        ),
        ActivitySector(
            100012,
            0,
            "TOURISME, HOTELLERIE-RESTAURATION, SPORTS & LOISIRS",
            12,
            1,
            12,
            False,
            None,
        ),
        ActivitySector(
            100013, 0, "BTP, CONSTRUCTION, INFRASTRUCTURES", 13, 1, 13, False, None
        ),
        ActivitySector(100014, 0, "TRANSPORT, LOGISTIQUE", 14, 1, 14, False, None),
        ActivitySector(100015, 0, "INDUSTRIE AUTOMOBILE", 15, 1, 15, False, None),
        ActivitySector(100016, 0, "EQUIPEMENTS INDUSTRIELS", 16, 1, 16, False, None),
        ActivitySector(100017, 0, "SECURITE, SURETE, DEFENSE", 17, 1, 17, False, None),
        ActivitySector(
            100018,
            0,
            "SERVICES, FORMATION, ENSEIGNEMENT, RESSOURCES HUMAINES",
            18,
            1,
            18,
            False,
            None,
        ),
        ActivitySector(100019, 0, "FINANCE ET ASSURANCE", 19, 1, 19, False, None),
    ],
    specializations=[
        Specialization(
            19,
            "FI   ",
            "FINANCE COMPTABILITE GESTION BANQUE",
            "FINANCE ACCOUNTING CONTROLLING BANKING",
            0,
        ),
        Specialization(24, "SI   ", "SYSTEMES D'INFORMATION", "INFORMATION SYSTEMS", 0),
        Specialization(36, "AL   ", "ARTS ET LITTERATURE", "ART AND LITERATURE", 0),
        Specialization(
            58,
            "GP   ",
            "GESTION DE LA PRODUCTION INDUSTRIELLE",
            "INDUSTRIAL PRODUCTION MANAGEMENT",
            0,
        ),
        Specialization(
            59, "PI   ", "PRODUCTION INDUSTRIELLE", "INDUSTRIAL PRODUCTION", 0
        ),
        Specialization(
            81, "SP   ", "SANTE BEAUTE PARAMEDICAL", "HEALTH BEAUTY PARAMEDICAL", 0
        ),
        Specialization(89, "CS   ", "", "", 0),
    ],
)

geographic_zones_dataset = GeographicZonesDataset(
    result=[
        GeographicZone(1, "AFRIQUE SUBSAHARIENNE", "Sub-Saharan Africa"),
        GeographicZone(2, "AMERIQUE DU NORD", "North America"),
        GeographicZone(3, "AMERIQUE LATINE", "Latin America"),
        GeographicZone(4, "ASIE ET PACIFIQUE", "Asia and Pacific"),
        GeographicZone(5, "EUROPE OCCIDENTALE", "Western Europe"),
        GeographicZone(6, "EUROPE CENTRALE ET ORIENTALE", "Central and Eastern Europe"),
        GeographicZone(7, "AFRIQUE DU NORD", "North Africa"),
        GeographicZone(8, "PROCHE ET MOYEN ORIENT", "Near and Middle East"),
    ],
    count=8,
    fileShareUrl=None,
    logosContainer=None,
    fileShareSasToken=None,
)
