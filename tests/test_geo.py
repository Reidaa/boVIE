from bovie.job.models.geozone import get_zone_id_from_name, get_zone_ids, get_zone_names


def test_get_zone_names():
    expected = [
        "afrique du nord",
        "afrique subsaharienne",
        "amerique du nord",
        "amerique latine",
        "asie et pacifique",
        "europe occidentale",
        "europe centrale et orientale",
        "proche et moyen orient",
    ]

    result = get_zone_names()

    assert sorted(result) == sorted(expected)

def test_get_zone_ids():
    expected = ["1", "2", "3", "4", "5", "6", "7", "8"]

    result = get_zone_ids()

    assert sorted(result) == sorted(expected)

def test_get_zone_ids_from_name():
    name = "afrique du nord"
    expected = "7"

    result = get_zone_id_from_name(name)

    assert result == expected


def test_get_zone_ids_from_name_mixed_case():
    name = "EUROPE OCCIDenTALE"
    expected = "5"

    result = get_zone_id_from_name(name)

    assert result == expected