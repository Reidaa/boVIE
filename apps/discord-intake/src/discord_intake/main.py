import asyncio

import click
import nats.errors
from cli_common import configure_logging, log_failure
from discord_store import accept
from mysql_common import make_engine
from mysql_common.env import load_env
from nats_client import CONSUMER, STREAM, connect, subject
from offer_events import OfferEvent
from sqlalchemy.engine import Engine

# A failing message is retried until it succeeds. JetStream keeps it, so a fix
# deployed later still delivers it. The delay doubles from 30 s up to this cap.
MAX_RETRY_DELAY = 3600


async def receive_message(engine: Engine, message):
    event = OfferEvent.model_validate_json(message.data)
    if message.subject != subject(event.source):
        raise ValueError("Event source does not match its NATS subject")
    await asyncio.to_thread(accept, engine, event)
    await message.ack_sync(timeout=10)


def retry_delay(deliveries: int) -> int:
    return min(30 * 2 ** (deliveries - 1), MAX_RETRY_DELAY)


async def handle(engine: Engine, message) -> bool:
    """Process one message; on failure, log it and schedule its next delivery."""
    try:
        await receive_message(engine, message)
    except Exception as error:  # noqa: BLE001 - any failure is logged and retried
        deliveries = message.metadata.num_delivered
        log_failure(
            error,
            f"Discord intake of stream message {message.metadata.sequence.stream} "
            f"(delivery {deliveries})",
        )
        await message.nak(delay=retry_delay(deliveries))
        return False
    return True


@click.command()
@click.option(
    "--once", is_flag=True, help="Drain currently available messages and exit."
)
def main(once: bool):
    """Commit events and pending Discord deliveries before acknowledging NATS."""
    configure_logging()
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
                    if not await handle(engine, message) and once:
                        raise click.ClickException("Ingestion failed; message retained")
        finally:
            await nc.close()

    try:
        asyncio.run(run())
    finally:
        engine.dispose()
