import pytest
from collector_business_france.job.models.job import Job
from collector_business_france.job.models.search import SearchParameters
from sqlalchemy import func, select


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


def test_interrupted_collection_replays_without_skipping(collector_db, monkeypatch):
    from collector_business_france import main
    from collector_store import Offer

    def search(params):
        return {0: [1, 2], 2: [3]}[params.skip]

    monkeypatch.setattr(main, "search_id", search)

    def interrupted(identity):
        if identity == 3:
            raise RuntimeError("upstream failure")
        return job(identity)

    published = []
    monkeypatch.setattr(main, "get_from_id", interrupted)
    with pytest.raises(RuntimeError):
        main.task(
            SearchParameters(limit=3), collector_db, published.append, page_size=2
        )
    assert [event.source_offer_id for event in published] == ["1", "2"]
    monkeypatch.setattr(main, "get_from_id", job)
    main.task(SearchParameters(limit=3), collector_db, published.append, page_size=2)
    main.task(SearchParameters(limit=3), collector_db, published.append, page_size=2)
    assert [event.source_offer_id for event in published] == ["1", "2", "3"]
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 3


def test_failed_publish_leaves_page_unrecorded(collector_db, monkeypatch):
    from collector_business_france import main
    from collector_store import Checkpoint, Offer

    monkeypatch.setattr(main, "search_id", lambda params: [1, 2])
    monkeypatch.setattr(main, "get_from_id", job)
    published = []

    def lose_second_ack(event):
        published.append(event)
        if len(published) == 2:
            raise TimeoutError("Lost publish acknowledgment")

    with pytest.raises(TimeoutError):
        main.task(SearchParameters(limit=2), collector_db, lose_second_ack)
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 0
        assert conn.scalar(select(func.count()).select_from(Checkpoint)) == 0
    main.task(SearchParameters(limit=2), collector_db, published.append)
    # The retry republishes both offers under the same event IDs.
    assert [event.event_id for event in published[2:]] == [
        event.event_id for event in published[:2]
    ]
    with collector_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Offer)) == 2


def test_business_france_preserves_display_fields():
    from collector_business_france.main import normalize

    event = normalize(job(1))
    assert event.source_offer_id == "1"
    assert event.offer.country == "Canada"
    assert len(event.offer.fields) == 14
