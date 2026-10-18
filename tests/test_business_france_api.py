import json

import httpx
import pytest
from collector_business_france import job
from collector_business_france.job.models.search import SearchParameters


def public_site(*keys):
    """Serve the public offers page, publishing each key in turn."""
    published = iter(keys)

    def page(request):
        key = next(published)
        return httpx.Response(200, text=f'<script>config:{{API_KEY:"{key}"}}</script>')

    return page


@pytest.fixture
def client(monkeypatch):
    """Replace the Business France client with one served by `handler`."""

    def install(handler):
        job.public_api_key.cache_clear()
        monkeypatch.setattr(
            job,
            "CLIENT",
            httpx.Client(base_url=job.URL, transport=httpx.MockTransport(handler)),
        )

    yield install
    job.public_api_key.cache_clear()


def test_business_france_search_uses_public_site_key_and_api_field_names(client):
    page = public_site("public\\/key")

    def handler(request):
        if str(request.url) == job.PUBLIC_OFFERS_URL:
            return page(request)
        assert request.url.path.endswith("/search")
        assert request.headers["X-API-KEY"] == "public/key"
        body = json.loads(request.content)
        assert body["geographicZones"] == ["5"]
        assert "gerographicZones" not in body
        return httpx.Response(200, json={"result": [{"id": 42}]})

    client(handler)
    assert job.search_id(SearchParameters(geographicZones=["5"])) == [42]


def test_rotated_key_is_fetched_again_and_the_request_retried(client):
    page = public_site("old", "new")
    sent = []

    def handler(request):
        if str(request.url) == job.PUBLIC_OFFERS_URL:
            return page(request)
        sent.append(request.headers["X-API-KEY"])
        if request.headers["X-API-KEY"] == "old":
            return httpx.Response(401)
        return httpx.Response(200, json={"result": [{"id": 7}]})

    client(handler)
    assert job.search_id(SearchParameters()) == [7]
    assert sent == ["old", "new"]


def test_a_second_unauthorized_response_fails_the_run(client):
    page = public_site("old", "still-wrong")

    def handler(request):
        if str(request.url) == job.PUBLIC_OFFERS_URL:
            return page(request)
        return httpx.Response(401)

    client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        job.search_id(SearchParameters())
