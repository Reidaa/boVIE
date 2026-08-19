import httpx

import bovie.job as job_api
from bovie.job.models.job import Job


def test_api_client_uses_api_key_header(monkeypatch):
    monkeypatch.setenv("BOVIE_API_KEY", "api-key")

    with job_api._create_client() as client:
        assert client.headers["X-API-KEY"] == "api-key"


def test_request_refreshes_expired_api_key(monkeypatch):
    requests = []

    def handler(request):
        requests.append((str(request.url), request.headers.get("X-API-KEY")))

        if str(request.url) == job_api.FRONTEND_URL:
            return httpx.Response(
                200,
                text='<script>window.__NUXT__={config:{API_KEY:"new\\u002Fkey="}}</script>',
            )

        if request.headers.get("X-API-KEY") == "old-key":
            return httpx.Response(401)

        return httpx.Response(200, json={"result": []})

    with httpx.Client(
        base_url=job_api.URL,
        headers={"X-API-KEY": "old-key"},
        transport=httpx.MockTransport(handler),
    ) as client:
        monkeypatch.setattr(job_api, "CLIENT", client)

        response = job_api._request("POST", "/search", json={})

    assert response.status_code == 200
    assert requests == [
        (f"{job_api.URL}/search", "old-key"),
        (job_api.FRONTEND_URL, "old-key"),
        (f"{job_api.URL}/search", "new/key="),
    ]


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
