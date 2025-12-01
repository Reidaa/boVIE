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
    limit: int, regions: tuple[str], specializations: tuple[str], countries: tuple[str]
) -> SearchConfig:
    regionIds: list[str] = []
    specializationsIds: list[str] = []
    countrieIds: list[str] = []

    for region in regions:
        tr = regionsFactory.get(region.lower().replace("_", " "))
        if tr is None:
            raise ValueError(f"Invalid geographic zone: {region}")
        regionIds.append(tr.value)

    for spec in specializations:
        temp_spe = specializationsFactory.get(spec.lower().replace("_", " "))
        if temp_spe is None:
            raise ValueError(f"Invalid specialization: {spec}")
        specializationsIds.append(temp_spe.value)

    for country in countries:
        temp_country = countriesFactory.get(country.lower().replace("_", " "))
        if temp_country is None:
            raise ValueError(f"Invalid country: {country}")
        countrieIds.append(temp_country.value)

    return SearchConfig(
        limit=limit,
        specializations=specializationsIds,
        regions=regionIds,
        countries=countrieIds,
    )


def configFromParams(
    limit: int, regions: tuple[str], specializations: tuple[str], countries: tuple[str]
) -> Config:
    return Config(
        search=parseSearch(
            limit=limit,
            specializations=specializations,
            regions=regions,
            countries=countries,
        )
    )
