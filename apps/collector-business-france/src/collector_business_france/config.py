from collections.abc import Iterable

from pydantic import BaseModel, PositiveInt

from .job.models.country import (
    get_countries_id_by_geographic_zone,
    get_country_code_from_name,
    get_country_ids,
    get_country_names,
)
from .job.models.geozone import get_zone_id_from_name, get_zone_names
from .job.models.specialization import (
    get_specialization_id_from_name,
    get_specialization_names,
)


class SearchConfig(BaseModel):
    limit: PositiveInt
    countries: Iterable[str] = []
    specializations: Iterable[str] = []


class Config(BaseModel):
    search: SearchConfig


def parse_search(
    limit: int,
    regions: Iterable[str],
    specializations: Iterable[str],
    countries: Iterable[str],
) -> SearchConfig:
    specialization_ids: set[str] = set()
    country_ids: set[str] = set()

    for spe in specializations:
        if spe.lower() not in get_specialization_names():
            raise ValueError(f"Invalid specialization: {spe}")

        spe_id = get_specialization_id_from_name(spe)
        if spe_id is None:
            raise ValueError(f"Invalid specialization: {spe}")

        specialization_ids.add(spe_id)

    for region in regions:
        if region.lower() not in get_zone_names():
            raise ValueError(f"Invalid geographic zone: {region}")

        zone_id = get_zone_id_from_name(region)
        if zone_id is None:
            raise ValueError(f"Invalid geographic zone: {region}")

        for country_id in get_countries_id_by_geographic_zone(zone_id):
            if country_id not in get_country_ids():
                raise ValueError(f"Invalid country from preset: {country_id}")
            country_ids.add(country_id)

    for country in countries:
        if country.lower() not in get_country_names():
            raise ValueError(f"Invalid country: {country}")
        country_id = get_country_code_from_name(country)
        if country_id is None:
            raise ValueError(f"Invalid country: {country}")
        country_ids.add(country_id)

    # Sorted, not set order: the collector hashes the search into its checkpoint
    # key, and set order changes with each process's hash seed.
    return SearchConfig(
        limit=limit,
        specializations=sorted(specialization_ids),
        countries=sorted(country_ids),
    )


def config_from_params(
    limit: int,
    regions: Iterable[str],
    specializations: Iterable[str],
    countries: Iterable[str],
) -> Config:
    return Config(
        search=parse_search(
            limit=limit,
            specializations=specializations,
            regions=regions,
            countries=countries,
        )
    )
