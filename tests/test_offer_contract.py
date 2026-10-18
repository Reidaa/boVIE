"""Messages already in the OFFERS stream must stay readable under `offers.*.v1`.

The samples in `contracts/offer_event_v1/` are frozen copies of published
messages. Never regenerate them to make this test pass: a change that breaks
them needs a new subject version (see docs/adr/0001).
"""

import json
from pathlib import Path

import pytest
from offer_events import OfferEvent

SAMPLES = sorted(
    (Path(__file__).parent / "contracts" / "offer_event_v1").glob("*.json")
)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda path: path.stem)
def test_published_v1_messages_still_parse(sample):
    OfferEvent.model_validate_json(sample.read_bytes())


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda path: path.stem)
def test_event_ids_stay_stable(sample):
    # Consumers drop republished events by ID; a new ID turns a replay into a duplicate.
    stored = json.loads(sample.read_bytes())
    stored_id = stored.pop("event_id")
    # Without an ID, the model derives it exactly as a collector does.
    assert str(OfferEvent.model_validate(stored).event_id) == stored_id


def test_samples_cover_every_event_type():
    assert {json.loads(path.read_bytes())["type"] for path in SAMPLES} == {
        "discovered",
        "updated",
        "closed",
    }
