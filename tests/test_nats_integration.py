import asyncio
import os
from uuid import uuid4

import httpx
import nats
import pytest
from nats.js.api import ConsumerConfig
from sqlalchemy import func, select

from tests.test_collection import job
from tests.test_wttj import detail, hit


def test_both_sources_through_real_jetstream_and_captured_discord(
    database_factory, monkeypatch
):
    from bovie import main
    from bovie.job.models.search import SearchParameters
    from broker_setup.main import setup
    from discord_delivery.delivery import deliver_one
    from notification_intake.main import receive_message
    from notification_store import Delivery
    from outbox_relay.main import relay_one
    from wttf.main import collect

    url = os.environ.get("NATS_TEST_URL")
    if not url:
        pytest.skip("Set NATS_TEST_URL to a disposable JetStream server")
    business_france = database_factory("source")
    wttj = database_factory("source")
    notification = database_factory("notification")
    monkeypatch.setattr(main, "search_id", lambda params: [1])
    monkeypatch.setattr(main, "get_from_id", job)
    main.task(SearchParameters(limit=1), business_france)

    def source_handler(request):
        if request.url.path.endswith("/public/jobs"):
            return httpx.Response(
                200,
                json={
                    "data": [hit("wttj-1")],
                    "metadata": {"page": 1, "page_count": 1},
                },
            )
        return httpx.Response(200, json=detail("wttj-1"))

    with httpx.Client(
        base_url="https://source.invalid", transport=httpx.MockTransport(source_handler)
    ) as client:
        collect(wttj, client)

    async def flow():
        nc = await nats.connect(url)
        js = nc.jetstream()
        stream = "TEST_" + uuid4().hex
        consumer = "notifications"
        try:
            await setup(js, stream=stream, consumer=consumer)
            # A short ack wait exercises broker redelivery after a lost consumer ack.
            await js.add_consumer(
                stream, config=ConsumerConfig(durable_name=consumer, ack_wait=0.2)
            )
            await relay_one(business_france, js, "business_france")
            await relay_one(wttj, js, "wttj")
            sub = await js.pull_subscribe_bind(durable=consumer, stream=stream)
            messages = await sub.fetch(2, timeout=2)
            from job_contracts import OfferDiscovered
            from notification_store import accept

            # Commit the first message but lose its acknowledgment.
            accept(notification, OfferDiscovered.model_validate_json(messages[0].data))
            await receive_message(notification, messages[1])
            replay = (await sub.fetch(1, timeout=2))[0]
            assert replay.data == messages[0].data
            await receive_message(notification, replay)
        finally:
            await js.delete_stream(stream)
            await nc.close()

    asyncio.run(flow())
    with notification.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 2
    sent = []

    def delivery_handler(request):
        sent.append(request)
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(delivery_handler)) as client:
        while deliver_one(notification, client, "https://discord.invalid/webhook"):
            pass
    assert len(sent) == 2
