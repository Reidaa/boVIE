from bovie.job.models.job import Job


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
