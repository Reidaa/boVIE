from collector_business_france.display import display_fields
from collector_business_france.job.models.job import Job
from collector_business_france.job.models.specialization import Specialization


def test_job_embed_displays_job_specializations():
    job = Job.model_construct(
        id=123,
        mission_title="Software Engineer",
        mission_start_date="2026-06-01T00:00:00",
        mission_end_date="2027-06-01T00:00:00",
        creation_date="2026-05-31T00:00:00",
        mission_duration=12,
        activity_sector_n1="Tech",
        organization_name="Example Corp",
        country_name="Canada",
        city_name="Montreal",
        indemnite=2500,
        contact_email="jobs@example.com",
        contact_name="Jane Doe",
        specializations=[
            Specialization(
                specializationId="24",
                specializationLabel="SYSTEMES ET LOGICIELS INFORMATIQUES",
                specializationLabelEn="INFORMATION SYSTEMS",
                specializationParentId=None,
            ),
            Specialization(
                specializationId="216",
                specializationLabel="MARKETING - COMMUNICATION",
                specializationLabelEn="MARKETING COMMUNICATION",
                specializationParentId=None,
            ),
        ],
    )

    embed = {"fields": [field.model_dump() for field in display_fields(job)]}

    assert {
        "inline": True,
        "name": ":label: Specialization(s)",
        "value": "SYSTEMES ET LOGICIELS INFORMATIQUES, MARKETING - COMMUNICATION",
    } in embed["fields"]
    assert {
        "inline": True,
        "name": ":outbox_tray: Application",
        "value": "Business France",
    } in embed["fields"]


def test_job_embed_displays_external_application_link():
    application_url = "https://prose.com/careers?ashby_jid=d93116e8"
    job = Job.model_construct(
        id=123,
        mission_title="Software Engineer",
        mission_start_date="2026-06-01T00:00:00",
        mission_end_date="2027-06-01T00:00:00",
        creation_date="2026-05-31T00:00:00",
        mission_duration=12,
        activity_sector_n1="Tech",
        organization_name="Example Corp",
        country_name="Canada",
        city_name="Montreal",
        indemnite=2500,
        contact_email="jobs@example.com",
        contact_name="Jane Doe",
        specializations=[],
        contact_url=application_url,
    )

    embed = {"fields": [field.model_dump() for field in display_fields(job)]}

    assert {
        "inline": True,
        "name": ":outbox_tray: Application",
        "value": f"[Site externe]({application_url})",
    } in embed["fields"]
