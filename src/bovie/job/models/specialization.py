import json
from typing import List

from pydantic import BaseModel, Field


class Specialization(BaseModel):
    id: str = Field(alias="specializationId")
    name: str = Field(alias="specializationLabelEn")
    parent_id: int | None = Field(alias="specializationParentId")

    class Config:
        validate_by_name = True


"""
GET /api/Offers/repository/search/dataset HTTP/1.1
Host: civiweb-api-prd.azurewebsites.net
"""
DATA_JSON = """
{
"specializations": [
    {
      "specializationId": "81",
      "specializationCode": "81",
      "specializationLabel": "SANTE BEAUTE PARAMEDICAL",
      "specializationLabelEn": "HEALTH BEAUTY PARAMEDICAL",
      "specializationParentId": null
    },
    {
      "specializationId": "190",
      "specializationCode": "190",
      "specializationLabel": "AGRI AGRO",
      "specializationLabelEn": "AGRI AND AGRO INDUSTRY",
      "specializationParentId": null
    },
    {
      "specializationId": "36",
      "specializationCode": "36",
      "specializationLabel": "ARTS ET LITTERATURE",
      "specializationLabelEn": "ART AND LITERATURE",
      "specializationParentId": null
    },
    {
      "specializationId": "216",
      "specializationCode": "216",
      "specializationLabel": "MARKETING - COMMUNICATION",
      "specializationLabelEn": "MARKETING COMMUNICATION",
      "specializationParentId": null
    },
    {
      "specializationId": "24",
      "specializationCode": "24",
      "specializationLabel": "SYSTEMES ET LOGICIELS INFORMATIQUES",
      "specializationLabelEn": "INFORMATION SYSTEMS",
      "specializationParentId": null
    },
    {
      "specializationId": "58",
      "specializationCode": "58",
      "specializationLabel": "GESTION DE LA PRODUCTION INDUSTRIELLE",
      "specializationLabelEn": "INDUSTRIAL PRODUCTION MANAGEMENT",
      "specializationParentId": null
    },
    {
      "specializationId": "212",
      "specializationCode": "212",
      "specializationLabel": "INFORMATIQUE SCIENTIFIQUE ET INDUSTRIELLE",
      "specializationLabelEn": "SCIENTIFIC AND INDUSTRIAL COMPUTING",
      "specializationParentId": null
    },
    {
      "specializationId": "100",
      "specializationCode": "100",
      "specializationLabel": "RESSOURCES HUMAINES",
      "specializationLabelEn": "HUMAN RESSOURCES",
      "specializationParentId": null
    },
    {
      "specializationId": "59",
      "specializationCode": "59",
      "specializationLabel": "PRODUCTION INDUSTRIELLE",
      "specializationLabelEn": "INDUSTRIAL PRODUCTION",
      "specializationParentId": null
    },
    {
      "specializationId": "193",
      "specializationCode": "193",
      "specializationLabel": "COMMERCE",
      "specializationLabelEn": "BUSINESS",
      "specializationParentId": null
    },
    {
      "specializationId": "239",
      "specializationCode": "239",
      "specializationLabel": "SCIENCES ACADEMIQUES",
      "specializationLabelEn": "ACADEMIC SCIENCES",
      "specializationParentId": null
    },
    {
      "specializationId": "243",
      "specializationCode": "243",
      "specializationLabel": "ACHATS LOGISTIQUE TRANSPORT",
      "specializationLabelEn": "PURCHASING LOGISTICS TRANSPORT",
      "specializationParentId": null
    },
    {
      "specializationId": "255",
      "specializationCode": "255",
      "specializationLabel": "SCIENCES DE LA NATURE",
      "specializationLabelEn": "NATURAL SCIENCES",
      "specializationParentId": null
    },
    {
      "specializationId": "19",
      "specializationCode": "19",
      "specializationLabel": "FINANCE COMPTABILITE GESTION BANQUE",
      "specializationLabelEn": "FINANCE ACCOUNTING CONTROLLING BANKING",
      "specializationParentId": null
    },
    {
      "specializationId": "89",
      "specializationCode": "89",
      "specializationLabel": "COMMERCES SERVICES",
      "specializationLabelEn": "BUSINESSES SERVICES",
      "specializationParentId": null
    },
    {
      "specializationId": "214",
      "specializationCode": "214",
      "specializationLabel": "DROIT - JURIDIQUE - FISCAL",
      "specializationLabelEn": "LAW & TAXATION",
      "specializationParentId": null
    },
    {
      "specializationId": "210",
      "specializationCode": "210",
      "specializationLabel": "INFORMATION ET MEDIAS",
      "specializationLabelEn": "INFORMATION MEDIA",
      "specializationParentId": null
    },
    {
      "specializationId": "227",
      "specializationCode": "227",
      "specializationLabel": "PUBLIC & PARAPUBLIC",
      "specializationLabelEn": "PUBLIC SECTOR",
      "specializationParentId": null
    },
    {
      "specializationId": "196",
      "specializationCode": "196",
      "specializationLabel": "CONSTRUCTION",
      "specializationLabelEn": "CONSTRUCTION",
      "specializationParentId": null
    }
  ]
}
"""

SPECIALIZATIONS: List[Specialization] = [
    Specialization(**item) for item in json.loads(DATA_JSON)["specializations"]
]


def get_specialization_names() -> List[str]:
    """Return the list of specialization names."""
    return [spec.name.lower() for spec in SPECIALIZATIONS]

def get_specialization_ids() -> List[str]:
    """Return the list of specialization IDs."""
    return [spec.id for spec in SPECIALIZATIONS]

def get_specialization_id_from_name(name: str) -> str | None:
    """Return the Specialization object matching the given name, or None if not found."""
    name_norm = name.strip().lower()
    for spec in SPECIALIZATIONS:
        if spec.name.lower() == name_norm:
            return spec.id
    return None