from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine


def hit(identity, contract="vie"):
    return {
        "reference": identity,
        "slug": identity,
        "contract_type": contract,
        "organization": {"name": "Example", "slug": "example"},
    }


def detail(identity, contract="vie"):
    return {
        "job": {
            "wttj_reference": identity,
            "slug": identity,
            "name": "Engineer",
            "contract_type": contract,
            "status": "published",
            "organization": {"name": "Example", "slug": "example"},
            "offices": [{"city": "Montreal", "country_code": "CA"}],
            "published_at": "2026-09-01T00:00:00Z",
            "salary_min": 2500,
        }
    }


def test_wttj_pagination_filtering_and_detail_normalization(source_db):
    from source_store import Offer, Outbox
    from wttf.main import collect

    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/public/jobs"):
            assert request.url.params["job_title"] == ""
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "data": [hit("first"), hit("full-time", "full_time")]
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
        return httpx.Response(
            200,
            json=detail(
                request.url.path.rsplit("/", 1)[-1],
                "full_time" if request.url.path.endswith("/full-time") else "vie",
            ),
        )

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        collect(source_db, client, limit=10, max_pages=5)
        collect(source_db, client, limit=10, max_pages=5)
    with source_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 3
        assert conn.scalar(select(func.count()).select_from(Outbox)) == 3
        payload = conn.scalar(
            select(Offer.payload).where(Offer.source_offer_id == "first")
        )
        assert payload["source"] == "wttj"
        assert payload["offer"]["country"] == "CA"
    assert sum(path.endswith("/full-time") for path in paths) == 1
    assert sum(path.endswith("/first") for path in paths) == 1


def test_wttj_failed_detail_does_not_commit_page(source_db):
    from source_store import Checkpoint, Outbox
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


@pytest.mark.parametrize(
    "contract",
    [
        "full_time",
        "part_time",
        "temporary",
        "internship",
        "apprenticeship",
        "freelance",
        "vie",
        "future_contract_type",
    ],
)
def test_all_contract_types_are_collected_by_default(monkeypatch, contract):
    import wttf.main as worker

    recorded = []
    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(
        worker,
        "record_page",
        lambda engine, events, scan, page: recorded.extend(events) or events,
    )

    def handler(request):
        if request.url.path.endswith("/public/jobs"):
            assert request.url.params["job_title"] == ""
            assert "contract_type" not in request.url.params
            return httpx.Response(
                200,
                json={
                    "data": [hit("job", contract)],
                    "metadata": {"page": 1, "page_count": 1},
                },
            )
        return httpx.Response(200, json=detail("job", contract))

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        worker.collect(Mock(spec=Engine), client)
    assert len(recorded) == 1
    assert recorded[0].source_offer_id == "job"
    assert (
        next(
            field.value for field in recorded[0].offer.fields if field.name == "Contrat"
        )
        == contract
    )


def test_optional_filters_and_publication_status(monkeypatch):
    import wttf.main as worker

    recorded = []
    fetched = []
    monkeypatch.setattr(worker, "seen", lambda engine, identity: identity == "seen")
    monkeypatch.setattr(
        worker,
        "record_page",
        lambda engine, events, scan, page: recorded.extend(events) or events,
    )

    def handler(request):
        if request.url.path.endswith("/public/jobs"):
            assert request.url.params["job_title"] == "engineer"
            return httpx.Response(
                200,
                json={
                    "data": [
                        hit("selected", "full_time"),
                        hit("intern", "internship"),
                        hit("excluded", "vie"),
                        hit("changed", "full_time"),
                        hit("draft", "full_time"),
                        hit("abroad", "full_time"),
                        hit("seen", "full_time"),
                    ],
                    "metadata": {"page": 1, "page_count": 1},
                },
            )
        identity = request.url.path.rsplit("/", 1)[-1]
        fetched.append(identity)
        job = detail(identity, "internship" if identity == "intern" else "full_time")
        if identity == "changed":
            job["job"]["contract_type"] = "vie"
        if identity == "draft":
            job["job"]["status"] = "draft"
        if identity == "abroad":
            job["job"]["offices"] = [{"city": "Paris", "country_code": "FR"}]
        if identity == "selected":
            job["job"]["offices"].insert(0, {"city": "Paris", "country_code": "FR"})
        return httpx.Response(200, json=job)

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        worker.collect(
            Mock(spec=Engine),
            client,
            query="engineer",
            countries=("CA",),
            contracts=("full_time", "internship"),
        )
    assert [event.source_offer_id for event in recorded] == ["selected", "intern"]
    assert "excluded" not in fetched
    assert "seen" not in fetched


def test_unfiltered_collection_still_rejects_unpublished_jobs(monkeypatch):
    import wttf.main as worker

    recorded = []
    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(
        worker,
        "record_page",
        lambda engine, events, scan, page: recorded.extend(events) or events,
    )

    def handler(request):
        if request.url.path.endswith("/public/jobs"):
            return httpx.Response(
                200,
                json={
                    "data": [hit("draft", "full_time")],
                    "metadata": {"page": 1, "page_count": 1},
                },
            )
        result = detail("draft", "full_time")
        result["job"]["status"] = "draft"
        return httpx.Response(200, json=result)

    with httpx.Client(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    ) as client:
        worker.collect(Mock(spec=Engine), client)
    assert recorded == []
