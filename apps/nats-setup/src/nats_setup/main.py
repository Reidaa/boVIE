"""Provision the job stream and notification consumer.

The stream keeps messages after consumers acknowledge them, so several
consumers can read it and a new consumer can replay the retained history.
"""

import asyncio
from dataclasses import replace

import click
from job_messaging import CONSUMER, STREAM, connect
from job_runtime import configure_logging
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DiscardPolicy,
    RetentionPolicy,
    StorageType,
    StreamConfig,
)
from nats.js.errors import NotFoundError

RETENTION_DAYS = 90
# Stream limits that NATS can change in place.
LIMITS = ("max_age", "max_bytes", "max_msg_size", "duplicate_window")


async def replace_work_queue(js, existing: StreamConfig, config: StreamConfig):
    """Replace an empty work-queue stream; NATS cannot change retention in place.

    The old stream is detached from the offer subjects before its messages are
    counted. Publishes in that window fail and the collector retries on its next
    run, so no acknowledged event can be deleted with the stream.
    """
    await js.update_stream(
        config=replace(existing, subjects=[f"retired.{existing.name}"])
    )
    pending = (await js.stream_info(existing.name)).state.messages
    if pending:
        await js.update_stream(config=existing)
        raise ValueError(
            f"Stream {existing.name} is a work queue with {pending} messages. "
            "Let notification intake drain it, then run setup again."
        )
    await js.delete_stream(existing.name)
    await js.add_stream(config=config)


async def setup(js, *, stream: str = STREAM, consumer: str = CONSUMER):
    config = StreamConfig(
        name=stream,
        subjects=["offers.*.v1"],
        storage=StorageType.FILE,
        retention=RetentionPolicy.LIMITS,
        max_age=RETENTION_DAYS * 24 * 60 * 60,
        discard=DiscardPolicy.NEW,
        max_bytes=1024 * 1024 * 1024,
        max_msg_size=131072,
        duplicate_window=120,
        num_replicas=1,
    )
    try:
        existing = await js.stream_info(stream)
    except NotFoundError:
        await js.add_stream(config=config)
    else:
        if existing.config.retention == RetentionPolicy.WORK_QUEUE:
            await replace_work_queue(js, existing.config, config)
        elif (
            existing.config.subjects != config.subjects
            or existing.config.storage != config.storage
            or existing.config.retention != config.retention
            or existing.config.discard != config.discard
        ):
            raise ValueError(
                "Existing stream settings differ; review them before deployment"
            )
        elif any(
            getattr(existing.config, limit) != getattr(config, limit)
            for limit in LIMITS
        ):
            await js.update_stream(config=config)
    try:
        existing_consumer = await js.consumer_info(stream, consumer)
    except NotFoundError:
        await js.add_consumer(
            stream,
            config=ConsumerConfig(
                durable_name=consumer,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=120,
                max_ack_pending=1000,
            ),
        )
    else:
        if existing_consumer.config.ack_policy != AckPolicy.EXPLICIT:
            raise ValueError("Notification consumer must use explicit acknowledgment")


@click.command()
def main():
    """Provision JetStream once using separate administrator credentials."""

    configure_logging()

    async def run():
        nc = await connect()
        try:
            await setup(nc.jetstream())
        finally:
            await nc.close()

    asyncio.run(run())
