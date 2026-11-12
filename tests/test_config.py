import pytest
from collector_business_france.config import config_from_params
from pydantic import ValidationError


def test_config_from_params():
    limit = 100
    zones = ["AMERIQUE DU NORD"]
    specializations = ["Information Systems"]
    countries = []

    config = config_from_params(
        limit=limit,
        regions=zones,
        specializations=specializations,
        countries=countries,
    )

    assert config.search.limit == limit
    assert len(specializations) == len(list(config.search.specializations))
    assert len(list(config.search.countries)) == 3


def test_config_from_params_invalid_region():
    limit = 100
    regions = ["Invalid Region"]
    specializations = ["Information Systems"]
    countries = ["Germany", "Canada"]

    with pytest.raises(ValueError, match="Invalid geographic zone"):
        config_from_params(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_specialization():
    limit = 100
    regions = ["AMERIQUE DU NORD"]
    specializations = ["Invalid Specialization"]
    countries = ["Germany", "Canada"]

    with pytest.raises(ValueError, match="Invalid specialization"):
        config_from_params(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_country():
    limit = 100
    regions = ["AMERIQUE DU NORD"]
    specializations = ["Information Systems"]
    countries = ["Invalid Country"]

    with pytest.raises(ValueError, match="Invalid country"):
        config_from_params(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_config_from_params_invalid_limit():
    limit = -10
    regions = ["AMERIQUE DU NORD"]
    specializations = ["Information Systems"]
    countries = []

    with pytest.raises(ValidationError):
        config_from_params(
            limit=limit,
            regions=regions,
            specializations=specializations,
            countries=countries,
        )


def test_search_ids_are_sorted():
    # The collector hashes the search into its checkpoint key. Set order changes
    # with each process's hash seed, so unsorted IDs give a new key on each run.
    config = config_from_params(
        limit=10,
        regions=["Europe Occidentale", "Asie et Pacifique"],
        specializations=["Information Systems", "Business", "Marketing Communication"],
        countries=[],
    )

    countries = list(config.search.countries)
    specializations = list(config.search.specializations)
    assert countries == sorted(countries)
    assert specializations == sorted(specializations)
