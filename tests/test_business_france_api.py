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
        monkeypatch.delenv("BUSINESS_FRANCE_API_KEY", raising=False)
        monkeypatch.setattr(job, "_api_key", None)
        monkeypatch.setattr(
            job,
            "CLIENT",
            httpx.Client(base_url=job.URL, transport=httpx.MockTransport(handler)),
        )

    return install


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
        sent.append((request.headers["X-API-KEY"], json.loads(request.content)))
        if request.headers["X-API-KEY"] == "old":
            return httpx.Response(401)
        return httpx.Response(200, json={"result": [{"id": 7}]})

    client(handler)
    assert job.search_id(SearchParameters(limit=3)) == [7]
    assert [key for key, _ in sent] == ["old", "new"]
    # The retry sends the same search, not an empty body.
    assert sent[0][1] == sent[1][1] and sent[1][1]["limit"] == 3


def test_configured_key_is_used_without_reading_the_site(client, monkeypatch):
    def handler(request):
        assert str(request.url) != job.PUBLIC_OFFERS_URL
        assert request.headers["X-API-KEY"] == "configured"
        return httpx.Response(200, json={"id": 1})

    client(handler)
    monkeypatch.setenv("BUSINESS_FRANCE_API_KEY", "configured")
    assert job._request("GET", "/details/1").json() == {"id": 1}


def test_stale_configured_key_is_replaced_once_per_run(client, monkeypatch):
    page = public_site("public")
    sent = []

    def handler(request):
        if str(request.url) == job.PUBLIC_OFFERS_URL:
            return page(request)
        sent.append(request.headers["X-API-KEY"])
        if request.headers["X-API-KEY"] == "stale":
            return httpx.Response(401)
        return httpx.Response(200, json={"id": 1})

    client(handler)
    monkeypatch.setenv("BUSINESS_FRANCE_API_KEY", "stale")
    job._request("GET", "/details/1")
    job._request("GET", "/details/2")
    assert sent == ["stale", "public", "public"]


def test_a_second_unauthorized_response_fails_the_run(client):
    page = public_site("old", "still-wrong")

    def handler(request):
        if str(request.url) == job.PUBLIC_OFFERS_URL:
            return page(request)
        return httpx.Response(401)

    client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        job.search_id(SearchParameters())


@pytest.mark.parametrize("status", [404, 410])
def test_offer_removed_before_its_details_are_read_is_none(client, status):
    client(lambda request: httpx.Response(status))
    job._api_key = "key"
    assert job.get_from_id(9) is None


def test_other_detail_failures_fail_the_run(client):
    client(lambda request: httpx.Response(503))
    job._api_key = "key"
    with pytest.raises(httpx.HTTPStatusError):
        job.get_from_id(9)
