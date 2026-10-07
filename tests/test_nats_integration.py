import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import httpx
import nats
import pytest
from nats.js.api import ConsumerConfig
from sqlalchemy import func, select

from tests.test_collection import job
from tests.test_wttj import detail, hit


def nats_url():
    url = os.environ.get("NATS_TEST_URL")
    if not url:
        pytest.skip("Set NATS_TEST_URL to a disposable JetStream server")
    return url


def test_both_sources_through_real_jetstream_and_captured_discord(
    database_factory, monkeypatch
):
    from collector_business_france import main
    from collector_business_france.job.models.search import SearchParameters
    from collector_wttj.main import collect
    from discord_intake.main import receive_message
    from discord_sender.delivery import deliver_one
    from job_messaging import Publisher
    from nats_setup.main import setup
    from notification_store import Delivery

    url = nats_url()
    monkeypatch.setenv("NATS_URL", url)
    monkeypatch.delenv("NATS_USER", raising=False)
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    business_france = database_factory("source")
    wttj = database_factory("source")
    notification = database_factory("notification")
    stream = "TEST_" + uuid4().hex
    consumer = "notifications"

    async def provision():
        nc = await nats.connect(url)
        js = nc.jetstream()
        await setup(js, stream=stream, consumer=consumer)
        # A short ack wait exercises broker redelivery after a lost consumer ack.
        await js.add_consumer(
            stream, config=ConsumerConfig(durable_name=consumer, ack_wait=0.2)
        )
        await nc.close()

    async def delete():
        nc = await nats.connect(url)
        await nc.jetstream().delete_stream(stream)
        await nc.close()

    asyncio.run(provision())
    try:
        monkeypatch.setattr(main, "search_id", lambda params: [1])
        monkeypatch.setattr(main, "get_from_id", job)

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

        published = []
        with Publisher() as publisher:

            def publish(event):
                publisher.publish(event)
                published.append(event)

            main.task(SearchParameters(limit=1), business_france, publish)
            with httpx.Client(
                base_url="https://source.invalid",
                transport=httpx.MockTransport(source_handler),
            ) as client:
                collect(wttj, client, publish)
            # A run that crashed before recording republishes the same event ID.
            publisher.publish(published[0])

        async def consume():
            nc = await nats.connect(url)
            js = nc.jetstream()
            try:
                sub = await js.pull_subscribe_bind(durable=consumer, stream=stream)
                messages = await sub.fetch(3, timeout=2)
                assert len(messages) == 2
                from job_contracts import OfferEvent
                from notification_store import accept

                # Commit the first message but lose its acknowledgment.
                accept(notification, OfferEvent.model_validate_json(messages[0].data))
                await receive_message(notification, messages[1])
                replay = (await sub.fetch(1, timeout=2))[0]
                assert replay.data == messages[0].data
                await receive_message(notification, replay)
                # Acknowledged messages stay in the stream for other consumers.
                assert (await js.stream_info(stream)).state.messages == 2
            finally:
                await nc.close()

        asyncio.run(consume())
    finally:
        asyncio.run(delete())
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


def test_setup_applies_changed_stream_limits():
    from nats_setup.main import setup

    url = nats_url()
    stream = "TEST_" + uuid4().hex

    async def flow():
        nc = await nats.connect(url)
        js = nc.jetstream()
        try:
            await setup(js, stream=stream)
            info = await js.stream_info(stream)
            await js.update_stream(
                config=replace(info.config, max_age=24 * 60 * 60, max_bytes=1024)
            )
            await setup(js, stream=stream)
            info = await js.stream_info(stream)
            assert info.config.max_age == 90 * 24 * 60 * 60
            assert info.config.max_bytes == 1024 * 1024 * 1024
        finally:
            await js.delete_stream(stream)
            await nc.close()

    asyncio.run(flow())
