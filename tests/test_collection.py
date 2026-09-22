import pytest
from sqlalchemy import func, select

from bovie.job.models.job import Job
from bovie.job.models.search import SearchParameters


def job(identity):
    return Job.model_construct(
        id=identity,
        missionTitle="Engineer",
        organizationName="Example",
        countryName="Canada",
        cityName="Montreal",
        missionStartDate="2026-06-01",
        missionEndDate="2027-06-01",
        creationDate="2026-05-01",
        missionDuration=12,
        activitySectorN1="Tech",
        indemnite=2500,
        contactEmail="jobs@example.com",
        contactName="Example",
        specializations=[],
    )


def test_interrupted_collection_replays_without_skipping(source_db, monkeypatch):
    from bovie import main
    from bovie.collector import Offer, Outbox

    def search(params):
        return {0: [1, 2], 2: [3]}[params.skip]

    monkeypatch.setattr(main, "search_id", search)

    def interrupted(identity):
        if identity == 3:
            raise RuntimeError("upstream failure")
        return job(identity)

    monkeypatch.setattr(main, "get_from_id", interrupted)
    with pytest.raises(RuntimeError):
        main.task(SearchParameters(limit=3), source_db, page_size=2)
    monkeypatch.setattr(main, "get_from_id", job)
    main.task(SearchParameters(limit=3), source_db, page_size=2)
    main.task(SearchParameters(limit=3), source_db, page_size=2)
    with source_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 3
        assert conn.scalar(select(func.count()).select_from(Outbox)) == 3


def test_business_france_preserves_notification_fields():
    from bovie.main import normalize

    event = normalize(job(1))
    assert event.source_offer_id == "1"
    assert event.offer.country == "Canada"
    assert len(event.offer.fields) == 14
