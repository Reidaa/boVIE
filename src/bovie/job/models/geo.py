import json
from typing import List

from pydantic import BaseModel, Field


class GeographicZone(BaseModel):
    id: str = Field(alias="geographicZoneId")
    name: str = Field(alias="geographicZoneLabelEn")

    class Config:
        validate_by_name = True

"""
GET /api/Offers/repository/geographic-zones HTTP/1.1
Host: civiweb-api-prd.azurewebsites.net
"""
GEO_DATA_JSON = """
{
  "result": [
    {
      "geographicZoneId": "1",
      "geographicZoneLabel": "AFRIQUE SUBSAHARIENNE",
      "geographicZoneLabelEn": "AFRIQUE SUBSAHARIENNE"
    },
    {
      "geographicZoneId": "2",
      "geographicZoneLabel": "AMERIQUE DU NORD",
      "geographicZoneLabelEn": "AMERIQUE DU NORD"
    },
    {
      "geographicZoneId": "3",
      "geographicZoneLabel": "AMERIQUE LATINE",
      "geographicZoneLabelEn": "AMERIQUE LATINE"
    },
    {
      "geographicZoneId": "4",
      "geographicZoneLabel": "ASIE ET PACIFIQUE",
      "geographicZoneLabelEn": "ASIE ET PACIFIQUE"
    },
    {
      "geographicZoneId": "5",
      "geographicZoneLabel": "EUROPE OCCIDENTALE",
      "geographicZoneLabelEn": "EUROPE OCCIDENTALE"
    },
    {
      "geographicZoneId": "6",
      "geographicZoneLabel": "EUROPE CENTRALE ET ORIENTALE",
      "geographicZoneLabelEn": "EUROPE CENTRALE ET ORIENTALE"
    },
    {
      "geographicZoneId": "7",
      "geographicZoneLabel": "AFRIQUE DU NORD",
      "geographicZoneLabelEn": "AFRIQUE DU NORD"
    },
    {
      "geographicZoneId": "8",
      "geographicZoneLabel": "PROCHE ET MOYEN ORIENT",
      "geographicZoneLabelEn": "PROCHE ET MOYEN ORIENT"
    }
  ],
  "count": 8,
  "fileShareUrl": null,
  "logosContainer": null,
  "fileShareSasToken": null
}
"""

ZONES: List[GeographicZone] = [
    GeographicZone(**item) for item in json.loads(GEO_DATA_JSON)["result"]
]


def get_zone_names() -> List[str]:
    """Return the list of geographic zone names."""
    return [zone.name.lower() for zone in ZONES]


def get_zone_ids() -> List[str]:
    """Return the list of geographic zone IDs."""
    return [zone.id for zone in ZONES]


def get_zone_id_from_name(name: str) -> str | None:
    """Return the GeographicZone object matching the given name, or None if not found."""
    name_norm = name.strip().lower()
    for zone in ZONES:
        if zone.name.lower() == name_norm:
            return zone.id
    return None
