import asyncio
import os

import nats
import nats.errors
import pytest

from tests.test_storage import event

PASSWORDS = {
    "nats-setup": "local-nats-setup",
    "collector-business-france": "local-nats-collector-business-france",
    "collector-wttj": "local-nats-collector-wttj",
    "collector-workday": "local-nats-collector-workday",
    "discord-intake": "local-nats-discord-intake",
}


def test_deployment_nats_permissions_and_durable_acknowledgments(monkeypatch):
    from discord_intake.main import ensure_consumer
    from nats_client import connect, ensure_stream

    url = os.environ.get("NATS_AUTH_TEST_URL")
    if not url:
        pytest.skip(
            "Set NATS_AUTH_TEST_URL to a disposable broker using deploy/nats.conf"
        )
    monkeypatch.setenv("NATS_URL", url)

    async def connect_as(user):
        monkeypatch.setenv("NATS_USER", user)
        monkeypatch.setenv("NATS_PASSWORD", PASSWORDS[user])
        return await connect()

    async def flow():
        connections = []
        try:
            # On an empty broker, the collectors create the stream themselves.
            for source, user in (
                ("business_france", "collector-business-france"),
                ("wttj", "collector-wttj"),
                ("workday", "collector-workday"),
            ):
                nc = await connect_as(user)
                connections.append(nc)
                await ensure_stream(nc.jetstream())
                discovered = event().model_copy(update={"source": source})
                await nc.jetstream().publish(
                    f"offers.{source}.v1", discovered.model_dump_json().encode()
                )
            receiver = await connect_as("discord-intake")
            connections.append(receiver)
            assert await ensure_consumer(receiver.jetstream())
            sub = await receiver.jetstream().pull_subscribe_bind(
                durable="discord-intake", stream="OFFERS"
            )
            for message in await sub.fetch(3, timeout=2):
                await message.ack_sync(timeout=2)

            # Each account can create only its own object, and change nothing.
            denied = {
                "collector-business-france": [
                    "offers.wttj.v1",
                    "_INBOX.discord-intake.>",
                    "$JS.API.STREAM.UPDATE.OFFERS",
                    "$JS.API.STREAM.DELETE.OFFERS",
                    "$JS.API.STREAM.CREATE.OTHER",
                ],
                "discord-intake": [
                    "$JS.API.CONSUMER.CREATE.OFFERS.other",
                    "$JS.API.CONSUMER.DELETE.OFFERS.discord-intake",
                ],
            }
            for user, subjects in denied.items():
                errors = asyncio.Queue()

                async def on_error(error, errors=errors):
                    await errors.put(error)

                nc = await nats.connect(
                    url, user=user, password=PASSWORDS[user], error_cb=on_error
                )
                connections.append(nc)
                for denied_subject in subjects:
                    if denied_subject.startswith("_INBOX."):
                        await nc.subscribe(denied_subject)
                    else:
                        await nc.publish(denied_subject, b"not permitted")
                await nc.flush()
                violations = [
                    str(await asyncio.wait_for(errors.get(), timeout=2)).lower()
                    for _ in subjects
                ]
                for denied_subject in subjects:
                    assert any(
                        f'"{denied_subject.lower()}"' in error for error in violations
                    )
        finally:
            for nc in connections:
                await nc.close()
            admin = await connect_as("nats-setup")
            await admin.jetstream().delete_stream("OFFERS")
            await admin.close()

    asyncio.run(flow())
