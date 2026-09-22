"""NATS JetStream transport; MySQL transactions end before any network operation."""

import asyncio
import os
import sys
import traceback

import click
import httpx
import nats
import nats.errors
from dotenv import load_dotenv
from loguru import logger
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DiscardPolicy,
    RetentionPolicy,
    StorageType,
    StreamConfig,
)
from nats.js.errors import NotFoundError
from sqlalchemy.engine import Engine

from bovie.collector import Outbox
from bovie.db import make_engine
from bovie.env import load_env
from bovie.events import OfferDiscovered
from bovie.notifications import accept, deliver_one
from bovie.queue import claim, finish, retry_later

STREAM = "OFFERS"
CONSUMER = "notifications"


def log_failure(error: Exception, operation: str):
    # Keep stack frames without exception messages or local values containing secrets.
    logger.error(
        "{} failed ({}).\n{}",
        operation,
        type(error).__name__,
        "".join(traceback.format_tb(error.__traceback__)),
    )


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


async def relay_one(engine: Engine, js, source: str) -> bool:
    work = await asyncio.to_thread(claim, engine, Outbox)
    if work is None:
        return False
    try:
        event = OfferDiscovered.model_validate(work.payload)
        if event.source != source:
            raise ValueError("Outbox event belongs to a different source")
        await js.publish(
            f"offers.{source}.v1",
            event.model_dump_json().encode(),
            headers={"Nats-Msg-Id": work.event_id},
            timeout=10,
        )
    except Exception:
        await asyncio.to_thread(retry_later, engine, Outbox, work)
        raise
    await asyncio.to_thread(finish, engine, Outbox, work)
    return True


async def receive_message(engine: Engine, message):
    event = OfferDiscovered.model_validate_json(message.data)
    if message.subject != f"offers.{event.source}.v1":
        raise ValueError("Event source does not match its NATS subject")
    await asyncio.to_thread(accept, engine, event)
    await message.ack_sync(timeout=10)


@click.group()
def cli():
    """Run the source relay or the independently owned notification service."""
    load_dotenv(".env", override=False)
    logger.remove()
    logger.add(sys.stderr, diagnose=False)


@cli.command("setup-nats")
def setup_nats():
    """Provision JetStream once using separate administrator credentials."""

    async def run():
        nc = await connect()
        try:
            await setup(nc.jetstream())
        finally:
            await nc.close()

    asyncio.run(run())


@cli.command()
@click.option("--source", required=True, type=click.Choice(["business_france", "wttj"]))
@click.option("--once", is_flag=True, help="Drain currently available work and exit.")
def relay(source: str, once: bool):
    """Publish this source's committed outbox to JetStream."""
    engine = make_engine(load_env().database_url)

    async def run():
        nc = await connect()
        try:
            while True:
                try:
                    processed = await relay_one(engine, nc.jetstream(), source)
                except Exception as error:
                    log_failure(error, "Relay")
                    if once:
                        raise click.ClickException(
                            "Relay failed; pending work retained"
                        ) from None
                    processed = False
                if not processed:
                    if once:
                        break
                    await asyncio.sleep(1)
        finally:
            await nc.close()

    try:
        asyncio.run(run())
    finally:
        engine.dispose()


@cli.command()
@click.option(
    "--once", is_flag=True, help="Drain currently available messages and exit."
)
def receive(once: bool):
    """Commit events and pending Discord deliveries before acknowledging NATS."""
    engine = make_engine(load_env().database_url)

    async def run():
        nc = await connect()
        try:
            subscription = await nc.jetstream().pull_subscribe_bind(
                durable=CONSUMER,
                stream=STREAM,
            )
            while True:
                try:
                    messages = await subscription.fetch(batch=1, timeout=2)
                except nats.errors.TimeoutError:
                    if once:
                        break
                    continue
                for message in messages:
                    try:
                        await receive_message(engine, message)
                    except Exception as error:
                        log_failure(error, "Notification ingestion")
                        await message.nak(delay=30)
                        if once:
                            raise click.ClickException(
                                "Ingestion failed; message retained"
                            ) from None
        finally:
            await nc.close()

    try:
        asyncio.run(run())
    finally:
        engine.dispose()


@cli.command()
@click.option(
    "--once", is_flag=True, help="Drain currently available deliveries and exit."
)
def deliver(once: bool):
    """Send committed pending deliveries using only notification credentials."""
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise click.ClickException("Set DISCORD_WEBHOOK_URL for the delivery process")
    engine = make_engine(load_env().database_url)

    async def run():
        with httpx.Client(timeout=15) as client:
            while True:
                try:
                    processed = await asyncio.to_thread(
                        deliver_one, engine, client, webhook
                    )
                except Exception as error:
                    log_failure(error, "Discord delivery")
                    if once:
                        raise click.ClickException(
                            "Delivery failed; pending work retained"
                        ) from None
                    processed = False
                if not processed:
                    if once:
                        break
                    await asyncio.sleep(1)

    try:
        asyncio.run(run())
    finally:
        engine.dispose()
