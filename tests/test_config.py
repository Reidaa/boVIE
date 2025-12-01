import pytest

from bovie.config import configFromParams


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
    assert 0 == len(list(config.search.regions))
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
