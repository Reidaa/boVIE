"""NATS connection settings shared by broker clients."""

import asyncio
import os
import threading
from typing import Self

import nats
from nats.js.api import DiscardPolicy, RetentionPolicy, StorageType, StreamConfig
from nats.js.errors import NotFoundError
from offer_events import OfferEvent

STREAM = "OFFERS"
CONSUMER = "discord-intake"
# Limits retention keeps acknowledged messages, so several consumers can read the
# stream and a new consumer can replay the retained history.
STREAM_CONFIG = StreamConfig(
    name=STREAM,
    subjects=["offers.*.v1"],
    storage=StorageType.FILE,
    retention=RetentionPolicy.LIMITS,
    max_age=90 * 24 * 60 * 60,
    discard=DiscardPolicy.NEW,
    max_bytes=1024 * 1024 * 1024,
    max_msg_size=131072,
    duplicate_window=120,
    num_replicas=1,
)


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
    )


async def ensure_stream(js):
    """Create the offer stream when it is missing. Never change an existing one.

    Collectors call this before they publish. Their accounts can create the
    stream but not update it, so an operator changes its limits with the
    nats-setup account.
    """
    try:
        await js.stream_info(STREAM)
    except NotFoundError:
        # When both collectors create it at once, both calls succeed:
        # JetStream accepts a create with the same configuration.
        await js.add_stream(config=STREAM_CONFIG)


class Publisher:
    """Publish events from synchronous collectors and wait for JetStream acks.

    The connection runs on its own event loop thread, so it keeps answering
    server pings while the collector blocks on HTTP or database calls.
    """

    def __init__(self, timeout: float = 10):
        self._timeout = timeout
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)

    def __enter__(self) -> Self:
        self._thread.start()
        try:
            self._nc = self._run(connect())
        except BaseException:
            self._stop()
            raise
        self._js = self._nc.jetstream()
        try:
            self._run(ensure_stream(self._js))
        except BaseException:
            self.__exit__()
            raise
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
