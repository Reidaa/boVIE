"""Normalize Business France display fields for discovery events."""

from dateutil.parser import isoparse
from offer_events import DisplayField

from collector_business_france.job.models.job import Job


def display_fields(job: Job) -> list[DisplayField]:
    start: str = isoparse(job.mission_start_date).strftime("%d/%m/%Y")
    end: str = isoparse(job.mission_end_date).strftime("%d/%m/%Y")
    specializations: str = (
        ", ".join([s.specialization_label for s in job.specializations])
        if job.specializations
        else "N/A"
    )

    if job.creation_date:
        posted: str = isoparse(job.creation_date).strftime("%d/%m/%Y")
    else:
        posted: str = "N/A"

    external_application_url = job.external_application_url
    application_value = (
        f"[Site externe]({external_application_url})"
        if external_application_url
        else "Business France"
    )

    fields = [
        {"name": ":hot_springs: Entreprise", "value": job.organization_name},
        {"name": ":satellite_orbital: Posté le", "value": posted},
        {"name": ":calendar: Durée", "value": f"{job.mission_duration} mois"},
        {
            "name": ":gear: Secteur",
            "value": job.activity_sector_n1 or "N/A",
        },
        {"name": ":world_map: Pays", "value": job.country_name},
        {"name": ":cityscape: Ville", "value": job.city_name or "N/A"},
        {"name": ":money_with_wings: Salaire", "value": f"{job.indemnite}e"},
        {"name": ":person_running: Début", "value": start},
        {"name": ":checkered_flag: Fin", "value": end},
        {
            "name": ":e_mail: Email",
            "value": job.contact_email or "N/A",
        },
        {
            "name": ":person_bald: Contact",
            "value": job.contact_name or "N/A",
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
