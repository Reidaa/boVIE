import json
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

API = "/wday/cxs/example/Careers"


def board(**overrides):
    from collector_workday.main import Board

    return Board.model_validate(
        {
            "url": "https://example.wd3.myworkdayjobs.com/en-US/Careers",
            "company": "Example",
        }
        | overrides
    )


def posting(identity):
    return {
        "title": "Engineer",
        "externalPath": f"/job/Paris/{identity}",
        "locationsText": "Paris",
        "postedOn": "Posted Today",
    }


def detail(identity, **info):
    return {
        "jobPostingInfo": {
            "id": "0123456789abcdef",
            "title": " Data Engineer ",
            "location": "Paris",
            "additionalLocations": ["Lyon"],
            "startDate": "2026-10-27",
            "endDate": "2026-11-05",
            "timeType": "Full time",
            "jobReqId": "R1",
            "jobPostingId": identity,
            "posted": True,
            "jobRequisitionLocation": {
                "descriptor": "Paris",
                "country": {"descriptor": "France", "alpha2Code": "FR"},
            },
        }
        | info,
        "hiringOrganization": {"name": "(1675) Internal entity", "url": ""},
    }


def pages(*pages, total=None):
    """Serve the given postings pages by offset, like Workday's 20-job pages."""
    size = len(pages[0]) if pages else 0

    def handler(request):
        if request.method == "POST":
            body = json.loads(request.content)
            index = body["offset"] // size if size else 0
            page = pages[index] if index < len(pages) else pages[0]
            count = sum(map(len, pages)) if total is None else total
            return httpx.Response(
                200,
                json={
                    "total": count if body["offset"] == 0 else 0,
                    "jobPostings": page,
                },
            )
        return httpx.Response(200, json=detail(request.url.path.rsplit("/", 1)[-1]))

    return handler


def run(engine, handler, boards, **kwargs):
    from collector_workday.main import collect

    published = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collect(engine, client, published.append, boards, delay=0, **kwargs)
    return published


def test_board_reads_tenant_host_and_site_from_its_public_url():
    from pydantic import ValidationError

    example = board()
    assert example.api_url == f"https://example.wd3.myworkdayjobs.com{API}"
    assert example.tenant == "example"
    assert example.site == "Careers"
    with pytest.raises(ValidationError):
        board(url="https://example.com/Careers")
    with pytest.raises(ValidationError):
        board(url="https://example.wd3.myworkdayjobs.com/")


def test_bundled_boards_are_valid():
    from collector_workday.main import load_boards

    boards = load_boards("")
    assert boards
    assert len({(b.tenant, b.site) for b in boards}) == len(boards)


def test_detail_normalization():
    from collector_workday.main import JobDetail, normalize

    job = JobDetail.model_validate(detail("Data-Engineer_R1")["jobPostingInfo"])
    event = normalize(board(), "/job/Paris/Data-Engineer_R1", job)
    assert event.source == "workday"
    assert event.source_offer_id == "example/Careers/Data-Engineer_R1"
    assert event.offer.title == "Data Engineer"
    assert event.offer.organization == "Example"
    assert event.offer.country == "FR"
    assert event.offer.city == "Paris"
    assert (
        str(event.offer.url)
        == "https://example.wd3.myworkdayjobs.com/Careers/job/Paris/Data-Engineer_R1"
    )
    assert {field.name: field.value for field in event.offer.fields} == {
        "Entreprise": "Example",
        "Lieu": "Paris, Lyon",
        "Publié le": "2026-10-27",
        "Contrat": "Full time",
        "Date limite": "2026-11-05",
        "Référence": "R1",
    }


def test_detail_normalization_without_optional_fields():
    from collector_workday.main import JobDetail, normalize

    job = JobDetail.model_validate(
        {"title": "Engineer", "jobPostingId": "Engineer_R2", "posted": True}
    )
    event = normalize(board(), "/job/x/Engineer_R2", job)
    assert (event.offer.country, event.offer.city) == ("N/A", "N/A")
    assert [field.name for field in event.offer.fields] == ["Entreprise", "Lieu"]


def test_pagination_records_offers_and_skips_known_ones(collector_db):
    from collector_store import Offer

    requests = []
    serve = pages(
        [posting(f"job-{i}") for i in range(20)],
        [posting("job-20"), posting("job-21")],
    )

    def handler(request):
        requests.append(request)
        return serve(request)

    first = run(collector_db, handler, [board()], limit=40)
    assert [event.source_offer_id.rsplit("/", 1)[-1] for event in first] == [
        f"job-{i}" for i in range(22)
    ]
    bodies = [json.loads(r.content) for r in requests if r.method == "POST"]
    assert bodies == [
        {"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}},
        {"limit": 20, "offset": 20, "searchText": "", "appliedFacets": {}},
    ]
    assert all(
        str(r.url).startswith(f"https://example.wd3.myworkdayjobs.com{API}/")
        for r in requests
    )
    requests.clear()
    assert run(collector_db, handler, [board()], limit=40) == []
    assert all(request.method == "POST" for request in requests)
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 22


def test_pagination_stops_at_limit_and_total(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(worker, "record_page", lambda *args: None)
    monkeypatch.setattr(worker, "require_recent_results", lambda *args: None)
    offsets = []
    full = [posting(f"job-{i}") for i in range(20)]
    serve = pages(full, full, full, total=40)

    def handler(request):
        if request.method == "POST":
            offsets.append(json.loads(request.content)["offset"])
        return serve(request)

    # Workday returns page 1 again past the end, so `total` must stop the scan.
    run(Mock(spec=Engine), handler, [board()], limit=100)
    assert offsets == [0, 20]
    offsets.clear()
    assert len(run(Mock(spec=Engine), handler, [board()], limit=25)) == 25
    assert offsets == [0, 20]


def test_filters_are_sent_in_the_search_body(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(worker, "record_page", lambda *args: None)
    monkeypatch.setattr(worker, "require_recent_results", lambda *args: None)
    bodies = []
    serve = pages([posting("job")])

    def handler(request):
        if request.method == "POST":
            bodies.append(json.loads(request.content))
        return serve(request)

    facets = {"locationCountry": ["54c5b6971ffb4bf0b116fe7651ec789a"]}
    filtered = board(searchText="data", appliedFacets=facets)
    run(Mock(spec=Engine), handler, [filtered])
    assert bodies[0]["searchText"] == "data"
    assert bodies[0]["appliedFacets"] == facets


def test_failed_page_keeps_earlier_pages_and_fails_the_run(collector_db):
    from collector_store import Checkpoint, Offer
    from collector_workday.main import CollectionFailed

    serve = pages([posting(f"job-{i}") for i in range(20)], [posting("job-20")])
    published = []

    def handler(request):
        if request.method == "POST" and json.loads(request.content)["offset"] == 20:
            return httpx.Response(503)
        return serve(request)

    from collector_workday.main import collect

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(CollectionFailed),
    ):
        collect(collector_db, client, published.append, [board()], delay=0)
    assert len(published) == 20
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 20
        assert conn.scalar(select(Checkpoint.offset)) == 0


def test_failed_detail_does_not_commit_page(collector_db):
    from collector_store import Checkpoint, Offer
    from collector_workday.main import CollectionFailed

    serve = pages([posting("first"), posting("second")])

    def handler(request):
        if request.url.path.endswith("/second"):
            return httpx.Response(503)
        return serve(request)

    with pytest.raises(CollectionFailed):
        run(collector_db, handler, [board()])
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 0
        assert conn.scalar(select(func.count()).select_from(Checkpoint)) == 0


def test_a_failed_board_does_not_stop_the_others(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(worker, "record_page", lambda *args: None)
    monkeypatch.setattr(worker, "require_recent_results", lambda *args: None)
    serve = pages([posting("job")])

    def handler(request):
        if request.url.host.startswith("broken."):
            return httpx.Response(422)
        return serve(request)

    broken = board(url="https://broken.wd1.myworkdayjobs.com/Careers")
    published = []
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(worker.CollectionFailed, match="broken/Careers"),
    ):
        worker.collect(
            Mock(spec=Engine), client, published.append, [broken, board()], delay=0
        )
    assert [event.source_offer_id for event in published] == ["example/Careers/job"]


def test_removed_and_unposted_jobs_are_skipped(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    monkeypatch.setattr(worker, "record_page", lambda *args: None)
    monkeypatch.setattr(worker, "require_recent_results", lambda *args: None)
    serve = pages([posting("gone"), posting("draft"), posting("open")])

    def handler(request):
        if request.url.path.endswith("/gone"):
            return httpx.Response(404, json={"errorCode": "S21"})
        if request.url.path.endswith("/draft"):
            return httpx.Response(200, json=detail("draft", posted=False))
        return serve(request)

    published = run(Mock(spec=Engine), handler, [board()])
    assert [event.source_offer_id for event in published] == ["example/Careers/open"]


def test_detail_identity_must_match_the_posting(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    serve = pages([posting("listed")])

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=detail("other"))
        return serve(request)

    with pytest.raises(worker.CollectionFailed):
        run(Mock(spec=Engine), handler, [board()])


def test_board_without_results_fails(collector_db):
    from collector_workday.main import CollectionFailed

    with pytest.raises(CollectionFailed, match="example/Careers"):
        run(collector_db, pages([]), [board()])


def test_a_broker_failure_stops_the_run(monkeypatch):
    import collector_workday.main as worker

    monkeypatch.setattr(worker, "seen", lambda engine, identity: False)
    hosts = []
    serve = pages([posting("job")])

    def handler(request):
        hosts.append(request.url.host)
        return serve(request)

    def publish(event):
        raise ConnectionError("broker down")

    second = board(url="https://second.wd1.myworkdayjobs.com/Careers")
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ConnectionError),
    ):
        worker.collect(Mock(spec=Engine), client, publish, [board(), second], delay=0)
    assert "second.wd1.myworkdayjobs.com" not in hosts
