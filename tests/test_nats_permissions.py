import asyncio
import os

import nats
import nats.errors
import pytest

from tests.test_storage import event


def test_deployment_nats_permissions_and_durable_acknowledgments(monkeypatch):
    from nats_client import connect
    from nats_setup.main import setup

    url = os.environ.get("NATS_AUTH_TEST_URL")
    if not url:
        pytest.skip(
            "Set NATS_AUTH_TEST_URL to a disposable broker using deploy/nats.conf"
        )

    async def flow():
        monkeypatch.setenv("NATS_URL", url)
        monkeypatch.setenv("NATS_USER", "nats-setup")
        monkeypatch.setenv("NATS_PASSWORD", "local-nats-setup")
        admin = await connect()
        connections = []
        try:
            await setup(admin.jetstream())
            for source, user, password in (
                (
                    "business_france",
                    "collector-business-france",
                    "local-nats-collector-business-france",
                ),
                ("wttj", "collector-wttj", "local-nats-collector-wttj"),
            ):
                monkeypatch.setenv("NATS_USER", user)
                monkeypatch.setenv("NATS_PASSWORD", password)
                nc = await connect()
                connections.append(nc)
                discovered = event().model_copy(update={"source": source})
                await nc.jetstream().publish(
                    f"offers.{source}.v1", discovered.model_dump_json().encode()
                )
            monkeypatch.setenv("NATS_USER", "discord-intake")
            monkeypatch.setenv("NATS_PASSWORD", "local-nats-discord-intake")
            receiver = await connect()
            connections.append(receiver)
            sub = await receiver.jetstream().pull_subscribe_bind(
                durable="discord-intake", stream="OFFERS"
            )
            for message in await sub.fetch(2, timeout=2):
                await message.ack_sync(timeout=2)
            errors = asyncio.Queue()

            async def on_error(error):
                await errors.put(error)

            denied = await nats.connect(
                url,
                user="collector-business-france",
                password="local-nats-collector-business-france",
                error_cb=on_error,
            )
            connections.append(denied)
            await denied.publish("offers.wttj.v1", b"not permitted")
            await denied.subscribe("_INBOX.discord-intake.>")
            await denied.flush()
            violations = [
                await asyncio.wait_for(errors.get(), timeout=2) for _ in range(2)
            ]
            assert all(isinstance(error, nats.errors.Error) for error in violations)
        finally:
            for nc in connections:
                await nc.close()
            await admin.jetstream().delete_stream("OFFERS")
            await admin.close()

    asyncio.run(flow())
