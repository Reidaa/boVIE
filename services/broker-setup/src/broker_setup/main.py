"""Provision the job stream and notification consumer."""

import asyncio

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


async def setup(js, *, stream: str = STREAM, consumer: str = CONSUMER):
    config = StreamConfig(
        name=stream,
        subjects=["offers.*.v1"],
        storage=StorageType.FILE,
        retention=RetentionPolicy.WORK_QUEUE,
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
        if (
            existing.config.subjects != config.subjects
            or existing.config.storage != config.storage
            or existing.config.retention != config.retention
            or existing.config.discard != config.discard
        ):
            raise ValueError(
                "Existing stream settings differ; review them before deployment"
            )
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
