import emoji
import hikari
from dateutil.parser import isoparse

from bovie.businessFrance.generated.models import Offer


class OfferEmbed(hikari.Embed):
    def __init__(self, offer: Offer):
        super().__init__(
            title=offer.missionTitle,
            description=None,
            url="https://mon-vie-via.businessfrance.fr/offres/recherche?query=",
            color=hikari.Color.from_hex_code("053599"),
            colour=None,
            timestamp=None,
        )

        start = isoparse(offer.missionStartDate).strftime("%d/%m/%Y")
        end = isoparse(offer.missionEndDate).strftime("%d/%m/%Y")

        self.add_field(
            emoji.emojize(":hot_springs: Entreprise"),
            value=offer.organizationName,
            inline=True,
        )
        self.add_field(
            emoji.emojize(":calendar: Durée"),
            value=f"{offer.missionDuration} mois",
            inline=True,
        )
        self.add_field(emoji.emojize(":gear: Secteur"), value=offer.activitySectorN1)
        self.add_field(
            emoji.emojize(":cityscape: Ville"), value=offer.cityName, inline=True
        )
        self.add_field(
            emoji.emojize(":world_map: Pays"), value=offer.countryName, inline=True
        )
        self.add_field(
            emoji.emojize(":money_with_wings: Salaire"),
            value=f"{offer.indemnite}e",
            inline=True,
        )
        self.add_field(
            emoji.emojize(":person_running: Début"),
            value=start,
            inline=True,
        )
        self.add_field(
            emoji.emojize(":chequered_flag: Fin"),
            value=end,
            inline=True,
        )
        self.add_field(
            emoji.emojize(":e_mail: Email"), value=offer.contactEmail, inline=True
        )
        self.add_field(
            emoji.emojize(":globe_with_meridians: Business France"),
            value=f"[Voir offre](ttps://mon-vie-via.businessfrance.fr/offres/{offer.id})",
            inline=True,
        )
        # if offer.contactName.strip() and offer.contactName is not None:
        #     self.add_field(
        #         emoji.emojize(":globe_with_meridians: LinkedIn"),
        #         value="[Voir Profil Recruteur](https://link)",
        #         inline=True,
        #     )
