"""NATS connection settings shared by broker clients."""

import os

import nats

STREAM = "OFFERS"
CONSUMER = "notifications"


async def connect():
    user = os.environ.get("NATS_USER")
    return await nats.connect(
        servers=[os.environ.get("NATS_URL", "nats://127.0.0.1:4222")],
        user=user,
        inbox_prefix=f"_INBOX.{user}" if user else "_INBOX",
        password=os.environ.get("NATS_PASSWORD"),
        connect_timeout=5,
        max_reconnect_attempts=3,
        reconnect_time_wait=1,
    )
