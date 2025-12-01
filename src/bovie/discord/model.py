from typing import List

from dateutil.parser import isoparse
from loguru import logger
from nextcord import Embed
from pydantic import BaseModel, Field

from bovie.job.models.job import Job


class EmbedField(BaseModel):
    name: str
    value: str
    inline: bool = Field(default=True)


class JobEmbed(Embed):
    def __init__(self, job: Job):
        super().__init__(
            title=job.missionTitle,
            color=341401,
        )

        start = isoparse(job.missionStartDate).strftime("%d/%m/%Y")
        end = isoparse(job.missionEndDate).strftime("%d/%m/%Y")

        fields: List[EmbedField] = [
            EmbedField(name=":hot_springs: Entreprise", value=job.organizationName),
            EmbedField(name=":calendar: Durée", value=f"{job.missionDuration} mois"),
            EmbedField(name=":gear: Secteur", value=job.activitySectorN1 if job.activitySectorN1 else "N/A"),
            EmbedField(name=":world_map: Pays", value=job.countryName),
            EmbedField(name=":cityscape: Ville", value=job.cityName if job.cityName else "N/A"),
            EmbedField(name=":money_with_wings: Salaire", value=f"{job.indemnite}e"),
            EmbedField(name=":person_running: Début", value=start),
            EmbedField(name=":checkered_flag: Fin", value=end),
            EmbedField(name=":e_mail: Email", value=job.contactEmail if job.contactEmail else "N/A"),
            EmbedField(name=":person_bald: Contact", value=job.contactName if job.contactName else "N/A"),
            EmbedField(
                name=":globe_with_meridians: Business France",
                value=f"[Voir offre](https://mon-vie-via.businessfrance.fr/offres/{job.id})",
            ),
        ]

        for f in fields:
            if not f.value:
                continue
            logger.debug(
                f"With offer ID {job.id} creating field '{f.name}' with value '{f.value}'"
            )
            self.add_field(name=f.name, value=f.value, inline=f.inline)
