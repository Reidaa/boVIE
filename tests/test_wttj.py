import httpx
import pytest
from sqlalchemy import func, select


def hit(identity, contract="vie"):
    return {
        "reference": identity,
        "slug": identity,
        "contract_type": contract,
        "organization": {"name": "Example", "slug": "example"},
    }


def detail(identity):
    return {
        "job": {
            "wttj_reference": identity,
            "slug": identity,
            "name": "VIE Engineer",
            "contract_type": "vie",
            "status": "published",
            "organization": {"name": "Example", "slug": "example"},
            "offices": [{"city": "Montreal", "country_code": "CA"}],
            "published_at": "2026-09-01T00:00:00Z",
            "salary_min": 2500,
        }
    }


def test_wttj_pagination_filtering_and_detail_normalization(source_db):
    from bovie.collector import Offer, Outbox
    from wttf.main import collect

    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/public/jobs"):
            assert request.url.params["job_title"] == "VIE"
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "data": [hit("first"), hit("ignored", "full_time")]
                    if page == 1
                    else [hit("second")],
                    "metadata": {
                        "page": page,
                        "page_count": 2,
                        "per_page": 2,
                        "total": 3,
                    },
                },
            )
        return httpx.Response(200, json=detail(request.url.path.rsplit("/", 1)[-1]))

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        collect(source_db, client, limit=10, max_pages=5)
        collect(source_db, client, limit=10, max_pages=5)
    with source_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 2
        assert conn.scalar(select(func.count()).select_from(Outbox)) == 2
        payload = conn.scalar(
            select(Offer.payload).where(Offer.source_offer_id == "first")
        )
        assert payload["source"] == "wttj"
        assert payload["offer"]["country"] == "CA"
    assert not any(path.endswith("/ignored") for path in paths)
    assert sum(path.endswith("/first") for path in paths) == 1


def test_wttj_failed_detail_does_not_commit_page(source_db):
    from bovie.collector import Checkpoint, Outbox
    from wttf.main import collect

    def handler(request):
        if request.url.path.endswith("/public/jobs"):
            return httpx.Response(
                200,
                json={
                    "data": [hit("first"), hit("second")],
                    "metadata": {"page": 1, "page_count": 1},
                },
            )
        if request.url.path.endswith("second"):
            return httpx.Response(503)
        return httpx.Response(200, json=detail("first"))

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            collect(source_db, client)
    with source_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Outbox)) == 0
        assert conn.scalar(select(func.count()).select_from(Checkpoint)) == 0
