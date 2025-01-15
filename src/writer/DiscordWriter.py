import logging
from dataclasses import dataclass, field
from typing import List

import httpx
from dateutil.parser import isoparse
from nextcord.embeds import Embed

from src.businessFrance.models import Offer
from src.writer.BaseWriter import BaseWriter

logger = logging.getLogger("discord_writer")


@dataclass
class Field:
    name: str
    value: str
    inline: bool = field(default_factory=lambda: True)


class OfferEmbed(Embed):
    def __init__(self, offer: Offer):
        super().__init__(
            title=offer.missionTitle,
            color=341401,
        )

        self._offer = offer

        start = isoparse(offer.missionStartDate).strftime("%d/%m/%Y")
        end = isoparse(offer.missionEndDate).strftime("%d/%m/%Y")

        fields: List[Field] = [
            Field(
                name=":hot_springs: Entreprise", value=offer.organizationName.strip()
            ),
            Field(name=":calendar: Durée", value=f"{offer.missionDuration} mois"),
            Field(name=":gear: Secteur", value=offer.activitySectorN1),
            Field(":world_map: Pays", offer.countryName),
            Field(":cityscape: Ville", offer.cityName),
            Field(":money_with_wings: Salaire", f"{offer.indemnite}e"),
            Field(":person_running: Début", start),
            Field(":checkered_flag: Fin", end),
            Field(":e_mail: Email", offer.contactEmail),
            Field(
                ":globe_with_meridians: Business France",
                f"[Voir offre](https://mon-vie-via.businessfrance.fr/offres/{offer.id})",
            ),
            Field(":person_bald: Contact", self._sanitize_contact_name()),
        ]

        for f in fields:
            logger.debug(
                f"With offer ID {offer.id} creating field '{f.name}' with value '{f.value}'"
            )
            self.add_field(name=f.name.strip(), value=f.value.strip(), inline=f.inline)

    def _sanitize_contact_name(self):
        name = self._offer.contactName

        if name is None:
            return "X"

        name = name.replace("Monsieur", "").replace("Madame", "").strip()

        if name == "":
            return "X"

        return name


class DiscordWriter(BaseWriter):
    """Handles posting offers to Discord"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def format_embed(self, offer: Offer):
        oe = OfferEmbed(offer)
        payload = {
            "content": "",
            "tts": False,
            "embeds": [oe.to_dict()],
            "components": [],
            "actions": {},
        }
        return payload

    def write(self, offer: Offer) -> bool:
        """Send offer notification to Discord"""
        payload = self.format_embed(offer)
        try:
            r = httpx.post(
                url=self.webhook_url,
                json=payload,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send Discord message: {str(e)}")
            return False

    def write_many(self, offers):
        return super().write_many(offers)
