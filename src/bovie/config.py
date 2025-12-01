from pydantic import BaseModel, PositiveInt

from .job.enum import Countries, Regions, Specializations


class SearchConfig(BaseModel):
    limit: PositiveInt
    regions: list[str] = []
    countries: list[str] = []
    specializations: list[str] = []


class Config(BaseModel):
    search: SearchConfig


regionsFactory = {
    name.lower().replace("_", " "): spec for name, spec in Regions.__members__.items()
}

regions_names = [name.lower().replace("_", " ") for name in Regions.__members__.keys()]

specializationsFactory = {
    name.lower().replace("_", " "): spec
    for name, spec in Specializations.__members__.items()
}

specialization_names = [
    name.lower().replace("_", " ") for name in Specializations.__members__.keys()
]

countriesFactory = {
    name.lower().replace("_", " "): spec for name, spec in Countries.__members__.items()
}

countries_names = [
    name.lower().replace("_", " ") for name in Countries.__members__.keys()
]


def parseSearch(
    limit: int, regions: list[str], specializations: list[str], countries: list[str]
) -> SearchConfig:
    regionIds: list[str] = []
    specializationsIds: list[str] = []
    countrieIds: list[str] = []

    for r in regions:
        t = regionsFactory.get(r.lower().replace("_", " "))
        if t is None:
            raise ValueError(f"Invalid geographic zone: {r}")
        regionIds.append(t.value)

    for spe in specializations:
        t = specializationsFactory.get(spe.lower().replace("_", " "))
        if t is None:
            raise ValueError(f"Invalid specialization: {spe}")
        specializationsIds.append(t.value)

    for countrie in countries:
        t = countriesFactory.get(countrie.lower().replace("_", " "))
        if t is None:
            raise ValueError(f"Invalid country: {countrie}")
        countrieIds.append(t.value)

    return SearchConfig(
        limit=limit,
        specializations=specializationsIds,
        regions=regionIds,
        countries=countrieIds,
    )


def configFromParams(
    limit: int, regions: list[str], specializations: list[str], countries: list[str]
) -> Config:
    return Config(
        search=parseSearch(
            limit=limit,
            specializations=specializations,
            regions=regions,
            countries=countries,
        )
    )
