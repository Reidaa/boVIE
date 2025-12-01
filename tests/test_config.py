import pytest

from bovie.config import configFromParams


def test_config_from_params():
    limit = 100
    regions = ["North America"]
    specializations = ["Information Systems"]
    countries = ["Germany", "Canada"]

    config = configFromParams(
        limit=limit,
        regions=regions,
        specializations=specializations,
        countries=countries,
    )

    assert config.search.limit == limit
    assert len(config.search.specializations) == len(specializations)
    assert len(config.search.regions) == len(regions)
    assert len(config.search.countries) == len(countries)


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
