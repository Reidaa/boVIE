from bovie.discord.model import JobEmbed
from bovie.job.models.job import Job
from bovie.job.models.specialization import Specialization


def test_job_embed_displays_job_specializations():
    job = Job.model_construct(
        id=123,
        missionTitle="Software Engineer",
        missionStartDate="2026-06-01T00:00:00",
        missionEndDate="2027-06-01T00:00:00",
        creationDate="2026-05-31T00:00:00",
        missionDuration=12,
        activitySectorN1="Tech",
        organizationName="Example Corp",
        countryName="Canada",
        cityName="Montreal",
        indemnite=2500,
        contactEmail="jobs@example.com",
        contactName="Jane Doe",
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

    embed = JobEmbed(job).to_dict()

    assert {
        "inline": True,
        "name": ":label: Specialization(s)",
        "value": "SYSTEMES ET LOGICIELS INFORMATIQUES, MARKETING - COMMUNICATION",
    } in embed["fields"]
