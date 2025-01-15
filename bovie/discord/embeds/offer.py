import logging
from typing import Dict, List

from nextcord import Embed, Color
from dateutil.parser import isoparse

from bovie.businessFrance.models import Offer

logger = logging.getLogger("bovie.discord.bot")


class OfferEmbed(Embed):
    def __init__(self, offer: Offer):
        super().__init__(
            title=offer.missionTitle,
            color=Color().from_rgb(5, 53, 153),
        )

        self._offer = offer

        start = isoparse(offer.missionStartDate).strftime("%d/%m/%Y")
        end = isoparse(offer.missionEndDate).strftime("%d/%m/%Y")

        fields: List[Dict[str, str | bool]] = [
            {
                "name": ":hot_springs: Entreprise",
                "value": offer.organizationName.strip(),
                "inline": True,
            },
            {
                "name": ":calendar: Durée",
                "value": f"{offer.missionDuration} mois",
                "inline": True,
            },
            {
                "name": ":gear: Secteur",
                "value": offer.activitySectorN1,
                "inline": True,
            },
            {
                "name": ":world_map: Pays",
                "value": offer.countryName,
                "inline": True,
            },
            {
                "name": ":cityscape: Ville",
                "value": offer.cityName,
                "inline": True,
            },
            {
                "name": ":money_with_wings: Salaire",
                "value": f"{offer.indemnite}e",
                "inline": True,
            },
            {
                "name": ":person_running: Début",
                "value": start,
                "inline": True,
            },
            {
                "name": ":checkered_flag: Fin",
                "value": end,
                "inline": True,
            },
            {
                "name": ":e_mail: Email",
                "value": offer.contactEmail,
                "inline": True,
            },
            {
                "name": ":globe_with_meridians: Business France",
                "value": f"[Voir offre](https://mon-vie-via.businessfrance.fr/offres/{offer.id})",
                "inline": True,
            },
            {
                "name": ":person_bald: Contact",
                "value": self._sanitize_contact_name(),
                "inline": True,
            },
        ]

        for f in fields:
            self.add_field(name=f["name"], value=f["value"].strip(), inline=f["inline"])

        # if offer.contactName.strip() and offer.contactName is not None:
        #     self.add_field(
        #         emoji.emojize(":globe_with_meridians: LinkedIn"),
        #         value="[Voir Profil Recruteur](https://link)",
        #         inline=True,
        #     )

    def _sanitize_contact_name(self):
        name = self._offer.contactName
        name = name.replace("Monsieur", "").replace("Madame", "").strip()

        if name is None or name == "":
            return "X"

        return name
