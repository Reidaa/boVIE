import asyncio
import os
from dataclasses import replace

import httpx
import nats
import nats.js.errors
import pytest
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
    from discord_intake.main import CONSUMER_CONFIG, ensure_consumer, receive_message
    from discord_sender.delivery import deliver_one
    from discord_store import Delivery
    from nats_client import CONSUMER, STREAM, Publisher

    url = nats_url()
    monkeypatch.setenv("NATS_URL", url)
    monkeypatch.delenv("NATS_USER", raising=False)
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    business_france = database_factory("collector")
    wttj = database_factory("collector")
    discord = database_factory("discord")
    stream = STREAM
    consumer = CONSUMER

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
                # The first collector run created the stream; intake adds its consumer.
                await ensure_consumer(js)
                # A short ack wait exercises broker redelivery after a lost consumer ack.
                await js.add_consumer(
                    stream, config=replace(CONSUMER_CONFIG, ack_wait=0.2)
                )
                sub = await js.pull_subscribe_bind(durable=consumer, stream=stream)
                messages = await sub.fetch(3, timeout=2)
                assert len(messages) == 2
                from discord_store import accept
                from offer_events import OfferEvent

                # Commit the first message but lose its acknowledgment.
                accept(discord, OfferEvent.model_validate_json(messages[0].data))
                await receive_message(discord, messages[1])
                replay = (await sub.fetch(1, timeout=2))[0]
                assert replay.data == messages[0].data
                await receive_message(discord, replay)
                # Acknowledged messages stay in the stream for other consumers.
                assert (await js.stream_info(stream)).state.messages == 2
            finally:
                await nc.close()

        asyncio.run(consume())
    finally:
        asyncio.run(delete_stream(url))
    with discord.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Delivery)) == 2
    sent = []

    def delivery_handler(request):
        sent.append(request)
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(delivery_handler)) as client:
        while deliver_one(discord, client, "https://discord.invalid/webhook"):
            pass
    assert len(sent) == 2


def test_existing_stream_keeps_its_limits():
    from nats_client import STREAM, STREAM_CONFIG, ensure_stream

    url = nats_url()

    async def flow():
        nc = await nats.connect(url)
        js = nc.jetstream()
        try:
            # An operator changed the limits; collectors must not undo that.
            await js.add_stream(config=replace(STREAM_CONFIG, max_bytes=1024))
            await ensure_stream(js)
            assert (await js.stream_info(STREAM)).config.max_bytes == 1024
        finally:
            await nc.close()
            await delete_stream(url)

    asyncio.run(flow())


def test_intake_waits_for_the_first_collector_to_create_the_stream(monkeypatch):
    from discord_intake import main
    from nats_client import CONSUMER, STREAM, ensure_stream

    url = nats_url()
    monkeypatch.setattr(main, "STREAM_WAIT", 0.1)

    async def flow():
        nc = await nats.connect(url)
        js = nc.jetstream()
        try:
            # `--once` has nothing to drain before the stream exists.
            assert not await main.ensure_consumer(js, wait=False)
            waiting = asyncio.create_task(main.ensure_consumer(js))
            await asyncio.sleep(0.3)
            assert not waiting.done()
            await ensure_stream(js)
            assert await asyncio.wait_for(waiting, timeout=2)
            assert (await js.consumer_info(STREAM, CONSUMER)).config.ack_wait == 120
        finally:
            await nc.close()
            await delete_stream(url)

    asyncio.run(flow())


async def delete_stream(url):
    """Remove the offer stream, so each test starts with an empty broker."""
    from nats_client import STREAM

    nc = await nats.connect(url)
    try:
        await nc.jetstream().delete_stream(STREAM)
    except nats.js.errors.NotFoundError:
        pass
    finally:
        await nc.close()
