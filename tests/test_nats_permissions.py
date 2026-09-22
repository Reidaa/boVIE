import asyncio
import os

import nats
import nats.errors
import pytest

from tests.test_storage import event


def test_deployment_nats_permissions_and_durable_acknowledgments(monkeypatch):
    from broker_setup.main import setup
    from job_messaging import connect

    url = os.environ.get("NATS_AUTH_TEST_URL")
    if not url:
        pytest.skip(
            "Set NATS_AUTH_TEST_URL to a disposable broker using deploy/nats.conf"
        )

    async def flow():
        monkeypatch.setenv("NATS_URL", url)
        monkeypatch.setenv("NATS_USER", "admin")
        monkeypatch.setenv("NATS_PASSWORD", "local-nats-admin")
        admin = await connect()
        connections = []
        try:
            await setup(admin.jetstream())
            for source, password in (
                ("business_france", "local-nats-bf"),
                ("wttj", "local-nats-wttj"),
            ):
                monkeypatch.setenv("NATS_USER", source)
                monkeypatch.setenv("NATS_PASSWORD", password)
                nc = await connect()
                connections.append(nc)
                discovered = event().model_copy(update={"source": source})
                await nc.jetstream().publish(
                    f"offers.{source}.v1", discovered.model_dump_json().encode()
                )
            monkeypatch.setenv("NATS_USER", "notifications")
            monkeypatch.setenv("NATS_PASSWORD", "local-nats-notifications")
            receiver = await connect()
            connections.append(receiver)
            sub = await receiver.jetstream().pull_subscribe_bind(
                durable="notifications", stream="OFFERS"
            )
            for message in await sub.fetch(2, timeout=2):
                await message.ack_sync(timeout=2)
            errors = asyncio.Queue()

            async def on_error(error):
                await errors.put(error)

            denied = await nats.connect(
                url, user="business_france", password="local-nats-bf", error_cb=on_error
            )
            connections.append(denied)
            await denied.publish("offers.wttj.v1", b"not permitted")
            await denied.subscribe("_INBOX.notifications.>")
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
