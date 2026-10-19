from collector_business_france.job.models.job import Job


def test_job_detects_external_application_url():
    url = "https://prose.com/careers?ashby_jid=d93116e8"

    job = Job.model_construct(contactURL=url)

    assert job.external_application_url == url


def test_job_ignores_internal_application_url():
    job = Job.model_construct(
        contactURL="https://mon-vie-via.businessfrance.fr/offres/244342"
    )

    assert job.external_application_url is None


def test_job_ignores_empty_application_url():
    job = Job.model_construct(contactURL="")

    assert job.external_application_url is None


def test_job_ignores_fields_the_collector_does_not_read():
    # Business France changes unused fields; only the fields shown on Discord matter.
    payload = {
        "id": 1,
        "missionTitle": "Engineer",
        "organizationName": "Example",
        "countryName": "Canada",
        "cityName": "Montreal",
        "cityAffectation": "Montreal",
        "missionStartDate": "2026-06-01",
        "missionEndDate": "2027-06-01",
        "creationDate": "2026-05-01",
        "missionDuration": 12,
        "activitySectorN1": "Tech",
        "indemnite": 2500,
        "contactEmail": None,
        "contactName": None,
        "specializations": None,
        "viewCounter": "unexpected",
    }

    job = Job.model_validate(payload, strict=True, by_alias=True)

    assert job.missionTitle == "Engineer"
