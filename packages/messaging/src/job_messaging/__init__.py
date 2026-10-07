"""NATS connection settings shared by broker clients."""

import asyncio
import os
import threading

import nats
from job_contracts import OfferEvent

STREAM = "OFFERS"
CONSUMER = "notifications"


def subject(source: str) -> str:
    return f"offers.{source}.v1"


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


class Publisher:
    """Publish events from synchronous collectors and wait for JetStream acks.

    The connection runs on its own event loop thread, so it keeps answering
    server pings while the collector blocks on HTTP or database calls.
    """

    def __init__(self, timeout: float = 10):
        self._timeout = timeout
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)

    def __enter__(self) -> "Publisher":
        self._thread.start()
        try:
            self._nc = self._run(connect())
        except BaseException:
            self._stop()
            raise
        self._js = self._nc.jetstream()
        return self

    def __exit__(self, *exc_info):
        try:
            self._run(self._nc.close())
        finally:
            self._stop()

    def publish(self, event: OfferEvent) -> None:
        self._run(
            self._js.publish(
                subject(event.source),
                event.model_dump_json().encode(),
                headers={"Nats-Msg-Id": str(event.event_id)},
                timeout=self._timeout,
            )
        )

    def _run(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    def _stop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()
