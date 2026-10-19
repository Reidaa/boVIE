import pytest
from collector_business_france.config import configFromParams


def test_config_from_params():
    limit = 100
    zones = ["AMERIQUE DU NORD"]
    specializations = ["Information Systems"]
    countries = []

    config = configFromParams(
        limit=limit,
        regions=zones,
        specializations=specializations,
        countries=countries,
    )

    assert config.search.limit == limit
    assert len(specializations) == len(list(config.search.specializations))
    assert 3 == len(list(config.search.countries))


def test_config_from_params_invalid_region():
    limit = 100
    regions = ["Invalid Region"]
    specializations = ["Information Systems"]
    countries = ["Germany", "Canada"]

    with pytest.raises(ValueError) as _:
        configFromParams(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_specialization():
    limit = 100
    regions = ["North America"]
    specializations = ["Invalid Specialization"]
    countries = ["Germany", "Canada"]

    with pytest.raises(ValueError) as _:
        configFromParams(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_country():
    limit = 100
    regions = ["North America"]
    specializations = ["Information Systems"]
    countries = ["Invalid Country"]

    with pytest.raises(ValueError) as _:
        configFromParams(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_limit():
    limit = -10
    regions = ["North America"]
    specializations = ["Information Systems"]
    countries = ["Germany", "Canada"]

    with pytest.raises(ValueError) as _:
        configFromParams(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_search_ids_are_sorted():
    # The collector hashes the search into its checkpoint key. Set order changes
    # with each process's hash seed, so unsorted IDs give a new key on each run.
    config = configFromParams(
        limit=10,
        regions=["Europe Occidentale", "Asie et Pacifique"],
        specializations=["Information Systems", "Business", "Marketing Communication"],
        countries=[],
    )

    countries = list(config.search.countries)
    specializations = list(config.search.specializations)
    assert countries == sorted(countries)
    assert specializations == sorted(specializations)
