"""Normalize Business France display fields for discovery events."""

from dateutil.parser import isoparse
from offer_events import DisplayField

from collector_business_france.job.models.job import Job


def display_fields(job: Job) -> list[DisplayField]:
    start: str = isoparse(job.missionStartDate).strftime("%d/%m/%Y")
    end: str = isoparse(job.missionEndDate).strftime("%d/%m/%Y")
    specializations: str = (
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
        {"name": ":hot_springs: Entreprise", "value": job.organizationName},
        {"name": ":satellite_orbital: Posté le", "value": posted},
        {"name": ":calendar: Durée", "value": f"{job.missionDuration} mois"},
        {
            "name": ":gear: Secteur",
            "value": job.activitySectorN1 if job.activitySectorN1 else "N/A",
        },
        {"name": ":world_map: Pays", "value": job.countryName},
        {"name": ":cityscape: Ville", "value": job.cityName if job.cityName else "N/A"},
        {"name": ":money_with_wings: Salaire", "value": f"{job.indemnite}e"},
        {"name": ":person_running: Début", "value": start},
        {"name": ":checkered_flag: Fin", "value": end},
        {
            "name": ":e_mail: Email",
            "value": job.contactEmail if job.contactEmail else "N/A",
        },
        {
            "name": ":person_bald: Contact",
            "value": job.contactName if job.contactName else "N/A",
        },
        {
            "name": ":globe_with_meridians: Business France",
            "value": f"[Voir offre](https://mon-vie-via.businessfrance.fr/offres/{job.id})",
        },
        {"name": ":outbox_tray: Application", "value": application_value},
        {"name": ":label: Specialization(s)", "value": specializations},
    ]

    # The event contract caps values at 1024 characters, like Discord's embed fields.
    return [
        DisplayField(name=field["name"], value=field["value"][:1024])
        for field in fields
        if field["value"]
    ]
