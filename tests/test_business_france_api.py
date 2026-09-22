import httpx
from bovie import job
from bovie.job.models.search import SearchParameters


def test_business_france_search_uses_public_site_key_and_api_field_names(monkeypatch):
    class Client:
        def get(self, url, **kwargs):
            assert url == job.PUBLIC_OFFERS_URL
            return httpx.Response(
                200,
                text='<script>config:{API_KEY:"public\\/key"}</script>',
                request=httpx.Request("GET", url),
            )

        def post(self, url, *, json, headers):
            assert url == "/search"
            assert headers == {"X-API-KEY": "public/key"}
            assert json["geographicZones"] == ["5"]
            assert "gerographicZones" not in json
            return httpx.Response(
                200,
                json={"result": [{"id": 42}]},
                request=httpx.Request("POST", job.URL + url),
            )

    job.public_api_key.cache_clear()
    monkeypatch.setattr(job, "CLIENT", Client())
    try:
        assert job.search_id(SearchParameters(geographicZones=["5"])) == [42]
    finally:
        job.public_api_key.cache_clear()
