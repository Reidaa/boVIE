from bovie.job.models.country import get_countries_id_by_geographic_zone
from bovie.job.models.geozone import get_zone_id_from_name


def test_get_countries_by_geographic_zone_from_id():
    expected = ["US", "CA", "BS"]

    result = get_countries_id_by_geographic_zone(2)

    assert sorted(result) == sorted(expected)


def test_get_countries_by_geographic_zone_from_value():
    expected = ["US", "CA", "BS"]
    zone = "Amerique du Nord"
    zone_id = get_zone_id_from_name(zone)

    assert zone_id is not None

    result = get_countries_id_by_geographic_zone(zone_id)

    assert sorted(expected) == sorted(result)
