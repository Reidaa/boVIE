import json
from typing import List, Optional

from pydantic import BaseModel, Field


class Country(BaseModel):
    country_id: str = Field(alias="countryId")
    name: str = Field(alias="countryNameEn")
    geographic_zone_id: str = Field(alias="geographicZoneId")

    class Config:
        validate_by_name = True

"""
POST /api/Offers/repository/geographic-zones/countries HTTP/1.1
Content-Length: 24
Content-Type: application/json
Host: civiweb-api-prd.azurewebsites.net

[1, 2, 3, 4, 5, 6, 7, 8]
"""
COUNTRIES_DATA_JSON = """
[
  {
    "countryId": "EG",
    "countryName": "EGYPTE",
    "countryNameEn": "EGYPTE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "SV",
    "countryName": "EL SALVADOR",
    "countryNameEn": "EL SALVADOR",
    "geographicZoneId": "3"
  },
  {
    "countryId": "AE",
    "countryName": "EMIRATS ARABES UNIS",
    "countryNameEn": "EMIRATS ARABES UNIS",
    "geographicZoneId": "8"
  },
  {
    "countryId": "EC",
    "countryName": "EQUATEUR",
    "countryNameEn": "EQUATEUR",
    "geographicZoneId": "3"
  },
  {
    "countryId": "ER",
    "countryName": "ERYTHREE",
    "countryNameEn": "ERYTHREE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "ES",
    "countryName": "ESPAGNE",
    "countryNameEn": "ESPAGNE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "EE",
    "countryName": "ESTONIE",
    "countryNameEn": "ESTONIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "US",
    "countryName": "ETATS-UNIS",
    "countryNameEn": "ETATS-UNIS",
    "geographicZoneId": "2"
  },
  {
    "countryId": "BW",
    "countryName": "BOTSWANA",
    "countryNameEn": "BOTSWANA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "BR",
    "countryName": "BRESIL",
    "countryNameEn": "BRESIL",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BN",
    "countryName": "BRUNEI DARUSSALAM",
    "countryNameEn": "BRUNEI DARUSSALAM",
    "geographicZoneId": "4"
  },
  {
    "countryId": "BG",
    "countryName": "BULGARIE",
    "countryNameEn": "BULGARIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "BF",
    "countryName": "BURKINA FASO",
    "countryNameEn": "BURKINA FASO",
    "geographicZoneId": "1"
  },
  {
    "countryId": "BI",
    "countryName": "BURUNDI",
    "countryNameEn": "BURUNDI",
    "geographicZoneId": "1"
  },
  {
    "countryId": "KH",
    "countryName": "CAMBODGE",
    "countryNameEn": "CAMBODGE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "CM",
    "countryName": "CAMEROUN",
    "countryNameEn": "CAMEROUN",
    "geographicZoneId": "1"
  },
  {
    "countryId": "CA",
    "countryName": "CANADA",
    "countryNameEn": "CANADA",
    "geographicZoneId": "2"
  },
  {
    "countryId": "CV",
    "countryName": "CAP-VERT",
    "countryNameEn": "CAP-VERT",
    "geographicZoneId": "1"
  },
  {
    "countryId": "CL",
    "countryName": "CHILI",
    "countryNameEn": "CHILI",
    "geographicZoneId": "3"
  },
  {
    "countryId": "ET",
    "countryName": "ETHIOPIE",
    "countryNameEn": "ETHIOPIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "FJ",
    "countryName": "FIDJI",
    "countryNameEn": "FIDJI",
    "geographicZoneId": "4"
  },
  {
    "countryId": "FI",
    "countryName": "FINLANDE",
    "countryNameEn": "FINLANDE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "GA",
    "countryName": "GABON",
    "countryNameEn": "GABON",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GM",
    "countryName": "GAMBIE",
    "countryNameEn": "GAMBIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GE",
    "countryName": "GEORGIE",
    "countryNameEn": "GEORGIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "GH",
    "countryName": "GHANA",
    "countryNameEn": "GHANA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GR",
    "countryName": "GRECE",
    "countryNameEn": "GRECE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "GD",
    "countryName": "GRENADE",
    "countryNameEn": "GRENADE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "GT",
    "countryName": "GUATEMALA",
    "countryNameEn": "GUATEMALA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "GN",
    "countryName": "GUINEE",
    "countryNameEn": "GUINEE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GQ",
    "countryName": "GUINEE EQUATORIALE",
    "countryNameEn": "GUINEE EQUATORIALE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GW",
    "countryName": "GUINEE-BISSAU",
    "countryNameEn": "GUINEE-BISSAU",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GY",
    "countryName": "GUYANA",
    "countryNameEn": "GUYANA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "HT",
    "countryName": "HAITI",
    "countryNameEn": "HAITI",
    "geographicZoneId": "3"
  },
  {
    "countryId": "HN",
    "countryName": "HONDURAS",
    "countryNameEn": "HONDURAS",
    "geographicZoneId": "3"
  },
  {
    "countryId": "HK",
    "countryName": "HONG KONG",
    "countryNameEn": "HONG KONG",
    "geographicZoneId": "4"
  },
  {
    "countryId": "LY",
    "countryName": "LIBYE",
    "countryNameEn": "LIBYE",
    "geographicZoneId": "7"
  },
  {
    "countryId": "LI",
    "countryName": "LIECHTENSTEIN",
    "countryNameEn": "LIECHTENSTEIN",
    "geographicZoneId": "5"
  },
  {
    "countryId": "LT",
    "countryName": "LITUANIE",
    "countryNameEn": "LITUANIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "LU",
    "countryName": "LUXEMBOURG",
    "countryNameEn": "LUXEMBOURG",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MO",
    "countryName": "MACAO",
    "countryNameEn": "MACAO",
    "geographicZoneId": "4"
  },
  {
    "countryId": "MK",
    "countryName": "MACEDOINE DU NORD",
    "countryNameEn": "MACEDOINE DU NORD",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MG",
    "countryName": "MADAGASCAR",
    "countryNameEn": "MADAGASCAR",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MY",
    "countryName": "MALAISIE",
    "countryNameEn": "MALAISIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "MW",
    "countryName": "MALAWI",
    "countryNameEn": "MALAWI",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MV",
    "countryName": "MALDIVES",
    "countryNameEn": "MALDIVES",
    "geographicZoneId": "4"
  },
  {
    "countryId": "ML",
    "countryName": "MALI",
    "countryNameEn": "MALI",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MT",
    "countryName": "MALTE",
    "countryNameEn": "MALTE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MA",
    "countryName": "MAROC",
    "countryNameEn": "MAROC",
    "geographicZoneId": "7"
  },
  {
    "countryId": "MU",
    "countryName": "MAURICE",
    "countryNameEn": "MAURICE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MR",
    "countryName": "MAURITANIE",
    "countryNameEn": "MAURITANIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MX",
    "countryName": "MEXIQUE",
    "countryNameEn": "MEXIQUE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "MD",
    "countryName": "MOLDAVIE",
    "countryNameEn": "MOLDAVIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "MC",
    "countryName": "MONACO",
    "countryNameEn": "MONACO",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MN",
    "countryName": "MONGOLIE",
    "countryNameEn": "MONGOLIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "ME",
    "countryName": "MONTENEGRO",
    "countryNameEn": "MONTENEGRO",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MZ",
    "countryName": "MOZAMBIQUE",
    "countryNameEn": "MOZAMBIQUE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "MM",
    "countryName": "MYANMAR / BIRMANIE",
    "countryNameEn": "MYANMAR / BIRMANIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "NA",
    "countryName": "NAMIBIE",
    "countryNameEn": "NAMIBIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "NR",
    "countryName": "NAURU",
    "countryNameEn": "NAURU",
    "geographicZoneId": "4"
  },
  {
    "countryId": "NP",
    "countryName": "NEPAL",
    "countryNameEn": "NEPAL",
    "geographicZoneId": "4"
  },
  {
    "countryId": "AL",
    "countryName": "ALBANIE",
    "countryNameEn": "ALBANIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "DZ",
    "countryName": "ALGERIE",
    "countryNameEn": "ALGERIE",
    "geographicZoneId": "7"
  },
  {
    "countryId": "DE",
    "countryName": "ALLEMAGNE",
    "countryNameEn": "ALLEMAGNE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "AD",
    "countryName": "ANDORRE",
    "countryNameEn": "ANDORRE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "AO",
    "countryName": "ANGOLA",
    "countryNameEn": "ANGOLA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "AG",
    "countryName": "ANTIGUA-ET-BARBUDA",
    "countryNameEn": "ANTIGUA-ET-BARBUDA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "SA",
    "countryName": "ARABIE SAOUDITE",
    "countryNameEn": "ARABIE SAOUDITE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "AR",
    "countryName": "ARGENTINE",
    "countryNameEn": "ARGENTINE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "AM",
    "countryName": "ARMENIE",
    "countryNameEn": "ARMENIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "AU",
    "countryName": "AUSTRALIE",
    "countryNameEn": "AUSTRALIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "AT",
    "countryName": "AUTRICHE",
    "countryNameEn": "AUTRICHE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "AZ",
    "countryName": "AZERBAIDJAN",
    "countryNameEn": "AZERBAIDJAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "BS",
    "countryName": "BAHAMAS",
    "countryNameEn": "BAHAMAS",
    "geographicZoneId": "2"
  },
  {
    "countryId": "BH",
    "countryName": "BAHREIN",
    "countryNameEn": "BAHREIN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "BD",
    "countryName": "BANGLADESH",
    "countryNameEn": "BANGLADESH",
    "geographicZoneId": "4"
  },
  {
    "countryId": "BB",
    "countryName": "BARBADE",
    "countryNameEn": "BARBADE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BE",
    "countryName": "BELGIQUE",
    "countryNameEn": "BELGIQUE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "BZ",
    "countryName": "BELIZE",
    "countryNameEn": "BELIZE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BJ",
    "countryName": "BENIN",
    "countryNameEn": "BENIN",
    "geographicZoneId": "1"
  },
  {
    "countryId": "BT",
    "countryName": "BHOUTAN",
    "countryNameEn": "BHOUTAN",
    "geographicZoneId": "4"
  },
  {
    "countryId": "BY",
    "countryName": "BIELORUSSIE",
    "countryNameEn": "BIELORUSSIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "BO",
    "countryName": "BOLIVIE",
    "countryNameEn": "BOLIVIE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BA",
    "countryName": "BOSNIE-HERZEGOVINE",
    "countryNameEn": "BOSNIE-HERZEGOVINE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "NI",
    "countryName": "NICARAGUA",
    "countryNameEn": "NICARAGUA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "NE",
    "countryName": "NIGER",
    "countryNameEn": "NIGER",
    "geographicZoneId": "1"
  },
  {
    "countryId": "NG",
    "countryName": "NIGERIA",
    "countryNameEn": "NIGERIA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "NO",
    "countryName": "NORVEGE",
    "countryNameEn": "NORVEGE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "NZ",
    "countryName": "NOUVELLE-ZELANDE",
    "countryNameEn": "NOUVELLE-ZELANDE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "OM",
    "countryName": "OMAN",
    "countryNameEn": "OMAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "UG",
    "countryName": "OUGANDA",
    "countryNameEn": "OUGANDA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "UZ",
    "countryName": "OUZBEKISTAN",
    "countryNameEn": "OUZBEKISTAN",
    "geographicZoneId": "6"
  },
  {
    "countryId": "PK",
    "countryName": "PAKISTAN",
    "countryNameEn": "PAKISTAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "PS",
    "countryName": "PALESTINE, ETAT DE",
    "countryNameEn": "PALESTINE, ETAT DE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "PA",
    "countryName": "PANAMA",
    "countryNameEn": "PANAMA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "PG",
    "countryName": "PAPOUASIE-NOUVELLE-GUINEE",
    "countryNameEn": "PAPOUASIE-NOUVELLE-GUINEE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "PY",
    "countryName": "PARAGUAY",
    "countryNameEn": "PARAGUAY",
    "geographicZoneId": "3"
  },
  {
    "countryId": "NL",
    "countryName": "PAYS-BAS",
    "countryNameEn": "PAYS-BAS",
    "geographicZoneId": "5"
  },
  {
    "countryId": "PE",
    "countryName": "PEROU",
    "countryNameEn": "PEROU",
    "geographicZoneId": "3"
  },
  {
    "countryId": "PH",
    "countryName": "PHILIPPINES",
    "countryNameEn": "PHILIPPINES",
    "geographicZoneId": "4"
  },
  {
    "countryId": "PL",
    "countryName": "POLOGNE",
    "countryNameEn": "POLOGNE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "PT",
    "countryName": "PORTUGAL",
    "countryNameEn": "PORTUGAL",
    "geographicZoneId": "5"
  },
  {
    "countryId": "QA",
    "countryName": "QATAR",
    "countryNameEn": "QATAR",
    "geographicZoneId": "8"
  },
  {
    "countryId": "CF",
    "countryName": "REPUBLIQUE CENTRAFRICAINE",
    "countryNameEn": "REPUBLIQUE CENTRAFRICAINE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "CD",
    "countryName": "REPUBLIQUE DEMOCRATIQUE DU CONGO",
    "countryNameEn": "REPUBLIQUE DEMOCRATIQUE DU CONGO",
    "geographicZoneId": "1"
  },
  {
    "countryId": "DO",
    "countryName": "REPUBLIQUE DOMINICAINE",
    "countryNameEn": "REPUBLIQUE DOMINICAINE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "CZ",
    "countryName": "TCHEQUIE / REPUBLIQUE TCHEQUE",
    "countryNameEn": "TCHEQUIE / REPUBLIQUE TCHEQUE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "RO",
    "countryName": "ROUMANIE",
    "countryNameEn": "ROUMANIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "FR",
    "countryName": "FRANCE",
    "countryNameEn": "FRANCE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CN",
    "countryName": "CHINE",
    "countryNameEn": "CHINE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "CY",
    "countryName": "CHYPRE",
    "countryNameEn": "CHYPRE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CO",
    "countryName": "COLOMBIE",
    "countryNameEn": "COLOMBIE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "KM",
    "countryName": "COMORES",
    "countryNameEn": "COMORES",
    "geographicZoneId": "1"
  },
  {
    "countryId": "CG",
    "countryName": "CONGO",
    "countryNameEn": "CONGO",
    "geographicZoneId": "1"
  },
  {
    "countryId": "KP",
    "countryName": "COREE DU NORD",
    "countryNameEn": "COREE DU NORD",
    "geographicZoneId": "4"
  },
  {
    "countryId": "KR",
    "countryName": "COREE DU SUD",
    "countryNameEn": "COREE DU SUD",
    "geographicZoneId": "4"
  },
  {
    "countryId": "CR",
    "countryName": "COSTA RICA",
    "countryNameEn": "COSTA RICA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "CI",
    "countryName": "COTE D'IVOIRE",
    "countryNameEn": "COTE D'IVOIRE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "HR",
    "countryName": "CROATIE",
    "countryNameEn": "CROATIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CU",
    "countryName": "CUBA",
    "countryNameEn": "CUBA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "DK",
    "countryName": "DANEMARK",
    "countryNameEn": "DANEMARK",
    "geographicZoneId": "5"
  },
  {
    "countryId": "DJ",
    "countryName": "DJIBOUTI",
    "countryNameEn": "DJIBOUTI",
    "geographicZoneId": "1"
  },
  {
    "countryId": "DM",
    "countryName": "DOMINIQUE",
    "countryNameEn": "DOMINIQUE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "AF",
    "countryName": "AFGHANISTAN",
    "countryNameEn": "AFGHANISTAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "ZA",
    "countryName": "AFRIQUE DU SUD",
    "countryNameEn": "AFRIQUE DU SUD",
    "geographicZoneId": "1"
  },
  {
    "countryId": "TJ",
    "countryName": "TADJIKISTAN",
    "countryNameEn": "TADJIKISTAN",
    "geographicZoneId": "6"
  },
  {
    "countryId": "TW",
    "countryName": "TAIWAN",
    "countryNameEn": "TAIWAN",
    "geographicZoneId": "4"
  },
  {
    "countryId": "TZ",
    "countryName": "TANZANIE",
    "countryNameEn": "TANZANIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "TD",
    "countryName": "TCHAD",
    "countryNameEn": "TCHAD",
    "geographicZoneId": "1"
  },
  {
    "countryId": "TH",
    "countryName": "THAILANDE",
    "countryNameEn": "THAILANDE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "TL",
    "countryName": "TIMOR-LESTE / TIMOR ORIENTAL",
    "countryNameEn": "TIMOR-LESTE / TIMOR ORIENTAL",
    "geographicZoneId": "4"
  },
  {
    "countryId": "TG",
    "countryName": "TOGO",
    "countryNameEn": "TOGO",
    "geographicZoneId": "1"
  },
  {
    "countryId": "TO",
    "countryName": "TONGA",
    "countryNameEn": "TONGA",
    "geographicZoneId": "4"
  },
  {
    "countryId": "TT",
    "countryName": "TRINITE-ET-TOBAGO",
    "countryNameEn": "TRINITE-ET-TOBAGO",
    "geographicZoneId": "3"
  },
  {
    "countryId": "TN",
    "countryName": "TUNISIE",
    "countryNameEn": "TUNISIE",
    "geographicZoneId": "7"
  },
  {
    "countryId": "TM",
    "countryName": "TURKMENISTAN",
    "countryNameEn": "TURKMENISTAN",
    "geographicZoneId": "6"
  },
  {
    "countryId": "TR",
    "countryName": "TURQUIE",
    "countryNameEn": "TURQUIE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "TV",
    "countryName": "TUVALU",
    "countryNameEn": "TUVALU",
    "geographicZoneId": "4"
  },
  {
    "countryId": "UA",
    "countryName": "UKRAINE",
    "countryNameEn": "UKRAINE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "UY",
    "countryName": "URUGUAY",
    "countryNameEn": "URUGUAY",
    "geographicZoneId": "3"
  },
  {
    "countryId": "VU",
    "countryName": "VANUATU",
    "countryNameEn": "VANUATU",
    "geographicZoneId": "4"
  },
  {
    "countryId": "VE",
    "countryName": "VENEZUELA",
    "countryNameEn": "VENEZUELA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "VN",
    "countryName": "VIET NAM",
    "countryNameEn": "VIET NAM",
    "geographicZoneId": "4"
  },
  {
    "countryId": "YE",
    "countryName": "YEMEN",
    "countryNameEn": "YEMEN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "ZM",
    "countryName": "ZAMBIE",
    "countryNameEn": "ZAMBIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "ZW",
    "countryName": "ZIMBABWE",
    "countryNameEn": "ZIMBABWE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "HU",
    "countryName": "HONGRIE",
    "countryNameEn": "HONGRIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "KY",
    "countryName": "ILES CAIMANS",
    "countryNameEn": "ILES CAIMANS",
    "geographicZoneId": "3"
  },
  {
    "countryId": "SB",
    "countryName": "ILES SALOMON",
    "countryNameEn": "ILES SALOMON",
    "geographicZoneId": "4"
  },
  {
    "countryId": "IN",
    "countryName": "INDE",
    "countryNameEn": "INDE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "ID",
    "countryName": "INDONESIE",
    "countryNameEn": "INDONESIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "IR",
    "countryName": "IRAN",
    "countryNameEn": "IRAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "IQ",
    "countryName": "IRAQ",
    "countryNameEn": "IRAQ",
    "geographicZoneId": "8"
  },
  {
    "countryId": "IE",
    "countryName": "IRLANDE",
    "countryNameEn": "IRLANDE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "IS",
    "countryName": "ISLANDE",
    "countryNameEn": "ISLANDE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "IL",
    "countryName": "ISRAËL",
    "countryNameEn": "ISRAËL",
    "geographicZoneId": "8"
  },
  {
    "countryId": "IT",
    "countryName": "ITALIE",
    "countryNameEn": "ITALIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "JM",
    "countryName": "JAMAIQUE",
    "countryNameEn": "JAMAIQUE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "JP",
    "countryName": "JAPON",
    "countryNameEn": "JAPON",
    "geographicZoneId": "4"
  },
  {
    "countryId": "JO",
    "countryName": "JORDANIE",
    "countryNameEn": "JORDANIE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "KZ",
    "countryName": "KAZAKHSTAN",
    "countryNameEn": "KAZAKHSTAN",
    "geographicZoneId": "6"
  },
  {
    "countryId": "KE",
    "countryName": "KENYA",
    "countryNameEn": "KENYA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "KG",
    "countryName": "KIRGHIZISTAN",
    "countryNameEn": "KIRGHIZISTAN",
    "geographicZoneId": "6"
  },
  {
    "countryId": "XK",
    "countryName": "KOSOVO",
    "countryNameEn": "KOSOVO",
    "geographicZoneId": "5"
  },
  {
    "countryId": "KW",
    "countryName": "KOWEIT",
    "countryNameEn": "KOWEIT",
    "geographicZoneId": "8"
  },
  {
    "countryId": "LA",
    "countryName": "LAOS",
    "countryNameEn": "LAOS",
    "geographicZoneId": "4"
  },
  {
    "countryId": "LS",
    "countryName": "LESOTHO",
    "countryNameEn": "LESOTHO",
    "geographicZoneId": "1"
  },
  {
    "countryId": "LV",
    "countryName": "LETTONIE",
    "countryNameEn": "LETTONIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "LB",
    "countryName": "LIBAN",
    "countryNameEn": "LIBAN",
    "geographicZoneId": "8"
  },
  {
    "countryId": "LR",
    "countryName": "LIBERIA",
    "countryNameEn": "LIBERIA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "GB",
    "countryName": "ROYAUME-UNI",
    "countryNameEn": "ROYAUME-UNI",
    "geographicZoneId": "5"
  },
  {
    "countryId": "RU",
    "countryName": "RUSSIE",
    "countryNameEn": "RUSSIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "RW",
    "countryName": "RWANDA",
    "countryNameEn": "RWANDA",
    "geographicZoneId": "1"
  },
  {
    "countryId": "LC",
    "countryName": "SAINTE-LUCIE",
    "countryNameEn": "SAINTE-LUCIE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "KN",
    "countryName": "SAINT-KITTS-ET-NEVIS",
    "countryNameEn": "SAINT-KITTS-ET-NEVIS",
    "geographicZoneId": "3"
  },
  {
    "countryId": "VA",
    "countryName": "SAINT-SIEGE",
    "countryNameEn": "SAINT-SIEGE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "VC",
    "countryName": "SAINT-VINCENT-ET-LES GRENADINES",
    "countryNameEn": "SAINT-VINCENT-ET-LES GRENADINES",
    "geographicZoneId": "3"
  },
  {
    "countryId": "WS",
    "countryName": "SAMOA",
    "countryNameEn": "SAMOA",
    "geographicZoneId": "4"
  },
  {
    "countryId": "ST",
    "countryName": "SAO TOME-ET-PRINCIPE",
    "countryNameEn": "SAO TOME-ET-PRINCIPE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SN",
    "countryName": "SENEGAL",
    "countryNameEn": "SENEGAL",
    "geographicZoneId": "1"
  },
  {
    "countryId": "RS",
    "countryName": "SERBIE",
    "countryNameEn": "SERBIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "SC",
    "countryName": "SEYCHELLES",
    "countryNameEn": "SEYCHELLES",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SL",
    "countryName": "SIERRA LEONE",
    "countryNameEn": "SIERRA LEONE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SG",
    "countryName": "SINGAPOUR",
    "countryNameEn": "SINGAPOUR",
    "geographicZoneId": "4"
  },
  {
    "countryId": "SK",
    "countryName": "SLOVAQUIE",
    "countryNameEn": "SLOVAQUIE",
    "geographicZoneId": "6"
  },
  {
    "countryId": "SI",
    "countryName": "SLOVENIE",
    "countryNameEn": "SLOVENIE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "SO",
    "countryName": "SOMALIE",
    "countryNameEn": "SOMALIE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SD",
    "countryName": "SOUDAN",
    "countryNameEn": "SOUDAN",
    "geographicZoneId": "1"
  },
  {
    "countryId": "LK",
    "countryName": "SRI LANKA",
    "countryNameEn": "SRI LANKA",
    "geographicZoneId": "4"
  },
  {
    "countryId": "SE",
    "countryName": "SUEDE",
    "countryNameEn": "SUEDE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CH",
    "countryName": "SUISSE",
    "countryNameEn": "SUISSE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "SR",
    "countryName": "SURINAME",
    "countryNameEn": "SURINAME",
    "geographicZoneId": "3"
  },
  {
    "countryId": "SZ",
    "countryName": "ESWATINI / SWAZILAND",
    "countryNameEn": "ESWATINI / SWAZILAND",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SY",
    "countryName": "SYRIE",
    "countryNameEn": "SYRIE",
    "geographicZoneId": "8"
  },
  {
    "countryId": "AQ",
    "countryName": "ANTARCTIQUE",
    "countryNameEn": "ANTARCTIQUE",
    "geographicZoneId": "3"
  },
  {
    "countryId": "AN",
    "countryName": "ANTILLES NEERLANDAISES",
    "countryNameEn": "ANTILLES NEERLANDAISES",
    "geographicZoneId": "3"
  },
  {
    "countryId": "AW",
    "countryName": "ARUBA",
    "countryNameEn": "ARUBA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BM",
    "countryName": "BERMUDES",
    "countryNameEn": "BERMUDES",
    "geographicZoneId": "3"
  },
  {
    "countryId": "BQ",
    "countryName": "BONAIRE, SAINT-EUSTACHE ET SABA",
    "countryNameEn": "BONAIRE, SAINT-EUSTACHE ET SABA",
    "geographicZoneId": "3"
  },
  {
    "countryId": "CW",
    "countryName": "CURACAO",
    "countryNameEn": "CURACAO",
    "geographicZoneId": "3"
  },
  {
    "countryId": "GS",
    "countryName": "GEORGIE DU SUD ET LES ILES SANDWICH DU SUD",
    "countryNameEn": "GEORGIE DU SUD ET LES ILES SANDWICH DU SUD",
    "geographicZoneId": "3"
  },
  {
    "countryId": "GI",
    "countryName": "GIBRALTAR",
    "countryNameEn": "GIBRALTAR",
    "geographicZoneId": "5"
  },
  {
    "countryId": "GL",
    "countryName": "GROENLAND",
    "countryNameEn": "GROENLAND",
    "geographicZoneId": "5"
  },
  {
    "countryId": "GU",
    "countryName": "GUAM",
    "countryNameEn": "GUAM",
    "geographicZoneId": "4"
  },
  {
    "countryId": "GG",
    "countryName": "GUERNESEY",
    "countryNameEn": "GUERNESEY",
    "geographicZoneId": "5"
  },
  {
    "countryId": "BV",
    "countryName": "ILE BOUVET",
    "countryNameEn": "ILE BOUVET",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CX",
    "countryName": "ILE CHRISTMAS",
    "countryNameEn": "ILE CHRISTMAS",
    "geographicZoneId": "4"
  },
  {
    "countryId": "IM",
    "countryName": "ILE DE MAN",
    "countryNameEn": "ILE DE MAN",
    "geographicZoneId": "5"
  },
  {
    "countryId": "HM",
    "countryName": "ILE HEARD ET ILES MACDONALD",
    "countryNameEn": "ILE HEARD ET ILES MACDONALD",
    "geographicZoneId": "4"
  },
  {
    "countryId": "NF",
    "countryName": "ILE NORFOLK",
    "countryNameEn": "ILE NORFOLK",
    "geographicZoneId": "4"
  },
  {
    "countryId": "AX",
    "countryName": "ILES ALAND",
    "countryNameEn": "ILES ALAND",
    "geographicZoneId": "5"
  },
  {
    "countryId": "CC",
    "countryName": "ILES COCOS (KEELING)",
    "countryNameEn": "ILES COCOS (KEELING)",
    "geographicZoneId": "4"
  },
  {
    "countryId": "CK",
    "countryName": "ILES COOK",
    "countryNameEn": "ILES COOK",
    "geographicZoneId": "4"
  },
  {
    "countryId": "FK",
    "countryName": "ILES FALKLAND",
    "countryNameEn": "ILES FALKLAND",
    "geographicZoneId": "3"
  },
  {
    "countryId": "FO",
    "countryName": "ILES FEROE",
    "countryNameEn": "ILES FEROE",
    "geographicZoneId": "5"
  },
  {
    "countryId": "MP",
    "countryName": "ILES MARIANNES DU NORD",
    "countryNameEn": "ILES MARIANNES DU NORD",
    "geographicZoneId": "4"
  },
  {
    "countryId": "MH",
    "countryName": "ILES MARSHALL",
    "countryNameEn": "ILES MARSHALL",
    "geographicZoneId": "4"
  },
  {
    "countryId": "UM",
    "countryName": "ILES MINEURES ELOIGNEES DES ETATS-UNIS",
    "countryNameEn": "ILES MINEURES ELOIGNEES DES ETATS-UNIS",
    "geographicZoneId": "4"
  },
  {
    "countryId": "TC",
    "countryName": "ILES TURKS-ET-CAICOS",
    "countryNameEn": "ILES TURKS-ET-CAICOS",
    "geographicZoneId": "3"
  },
  {
    "countryId": "VG",
    "countryName": "ILES VIERGES BRITANNIQUES",
    "countryNameEn": "ILES VIERGES BRITANNIQUES",
    "geographicZoneId": "3"
  },
  {
    "countryId": "VI",
    "countryName": "ILES VIERGES DES ETATS-UNIS",
    "countryNameEn": "ILES VIERGES DES ETATS-UNIS",
    "geographicZoneId": "3"
  },
  {
    "countryId": "JE",
    "countryName": "JERSEY",
    "countryNameEn": "JERSEY",
    "geographicZoneId": "5"
  },
  {
    "countryId": "KI",
    "countryName": "KIRIBATI",
    "countryNameEn": "KIRIBATI",
    "geographicZoneId": "4"
  },
  {
    "countryId": "FM",
    "countryName": "MICRONESIE",
    "countryNameEn": "MICRONESIE",
    "geographicZoneId": "4"
  },
  {
    "countryId": "MS",
    "countryName": "MONTSERRAT",
    "countryNameEn": "MONTSERRAT",
    "geographicZoneId": "3"
  },
  {
    "countryId": "PW",
    "countryName": "PALAOS",
    "countryNameEn": "PALAOS",
    "geographicZoneId": "4"
  },
  {
    "countryId": "PN",
    "countryName": "PITCAIRN",
    "countryNameEn": "PITCAIRN",
    "geographicZoneId": "4"
  },
  {
    "countryId": "PR",
    "countryName": "PORTO RICO",
    "countryNameEn": "PORTO RICO",
    "geographicZoneId": "3"
  },
  {
    "countryId": "EH",
    "countryName": "SAHARA OCCIDENTAL",
    "countryNameEn": "SAHARA OCCIDENTAL",
    "geographicZoneId": "7"
  },
  {
    "countryId": "SX",
    "countryName": "SAINT MARTIN (PARTIE NEERLANDAISE)",
    "countryNameEn": "SAINT MARTIN (PARTIE NEERLANDAISE)",
    "geographicZoneId": "3"
  },
  {
    "countryId": "SH",
    "countryName": "SAINTE-HELENE",
    "countryNameEn": "SAINTE-HELENE",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SM",
    "countryName": "SAINT-MARIN",
    "countryNameEn": "SAINT-MARIN",
    "geographicZoneId": "5"
  },
  {
    "countryId": "AS",
    "countryName": "SAMOA AMERICAINES",
    "countryNameEn": "SAMOA AMERICAINES",
    "geographicZoneId": "4"
  },
  {
    "countryId": "SS",
    "countryName": "SOUDAN DU SUD",
    "countryNameEn": "SOUDAN DU SUD",
    "geographicZoneId": "1"
  },
  {
    "countryId": "SJ",
    "countryName": "SVALBARD ET ILE JAN MAYEN",
    "countryNameEn": "SVALBARD ET ILE JAN MAYEN",
    "geographicZoneId": "5"
  },
  {
    "countryId": "IO",
    "countryName": "TERRITOIRE BRITANNIQUE DE L'OCEAN INDIEN",
    "countryNameEn": "TERRITOIRE BRITANNIQUE DE L'OCEAN INDIEN",
    "geographicZoneId": "1"
  },
  {
    "countryId": "TK",
    "countryName": "TOKELAU",
    "countryNameEn": "TOKELAU",
    "geographicZoneId": "4"
  }
]
""".replace("//", "#")  # si tu laisses les commentaires ci-dessus, on les neutralise

COUNTRIES: List[Country] = [Country(**item) for item in json.loads(COUNTRIES_DATA_JSON)]


def get_countries_id_by_geographic_zone(zone_id: int | str) -> list[str]:
    """
    Return the list of country IDs whose geographic zone matches zone_id.
    """
    zone_str = str(zone_id)
    return [c.country_id for c in COUNTRIES if c.geographic_zone_id == zone_str]


def get_country_names() -> list[str]:
    """Return the list of country English names."""
    return [c.name for c in COUNTRIES]


def get_country_ids() -> list[str]:
    """Return the list of country IDs."""
    return [c.country_id for c in COUNTRIES]


def get_country_code_from_name(country_name: str) -> Optional[str]:
    """Return the country code for a given country name (case insensitive)."""
    name_lower = country_name.lower()
    for country in COUNTRIES:
        if country.name.lower() == name_lower:
            return country.country_id
    return None
