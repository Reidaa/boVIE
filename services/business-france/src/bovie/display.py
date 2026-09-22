"""Normalize Business France display fields for discovery events."""

from dateutil.parser import isoparse
from job_contracts import DisplayField

from bovie.job.models.job import Job


def display_fields(job: Job) -> list[DisplayField]:
    start: str = isoparse(job.missionStartDate).strftime("%d/%m/%Y")
    end: str = isoparse(job.missionEndDate).strftime("%d/%m/%Y")
    categories: str = (
        ", ".join([s.specialization_label for s in job.specializations])
        if job.specializations
        else "N/A"
    )

    if job.creationDate:
        posted: str = isoparse(job.creationDate).strftime("%d/%m/%Y")
    else:
        posted: str = "N/A"

    external_application_url = job.external_application_url
    application_value = (
        f"[Site externe]({external_application_url})"
        if external_application_url
        else "Business France"
    )

    fields = [
        dict(name=":hot_springs: Entreprise", value=job.organizationName),
        dict(name=":satellite_orbital: Posté le", value=posted),
        dict(name=":calendar: Durée", value=f"{job.missionDuration} mois"),
        dict(
            name=":gear: Secteur",
            value=job.activitySectorN1 if job.activitySectorN1 else "N/A",
        ),
        dict(name=":world_map: Pays", value=job.countryName),
        dict(name=":cityscape: Ville", value=job.cityName if job.cityName else "N/A"),
        dict(name=":money_with_wings: Salaire", value=f"{job.indemnite}e"),
        dict(name=":person_running: Début", value=start),
        dict(name=":checkered_flag: Fin", value=end),
        dict(
            name=":e_mail: Email",
            value=job.contactEmail if job.contactEmail else "N/A",
        ),
        dict(
            name=":person_bald: Contact",
            value=job.contactName if job.contactName else "N/A",
        ),
        dict(
            name=":globe_with_meridians: Business France",
            value=f"[Voir offre](https://mon-vie-via.businessfrance.fr/offres/{job.id})",
        ),
        dict(name=":outbox_tray: Application", value=application_value),
        dict(name=":label: Category(ies)", value=categories),
    ]

    return [DisplayField.model_validate(field) for field in fields if field["value"]]
