import asyncio

import click
import nats.errors
from job_contracts import OfferDiscovered
from job_database import make_engine
from job_database.env import load_env
from job_messaging import CONSUMER, STREAM, connect
from job_runtime import configure_logging, log_failure
from notification_store import accept
from sqlalchemy.engine import Engine


async def receive_message(engine: Engine, message):
    event = OfferDiscovered.model_validate_json(message.data)
    if message.subject != f"offers.{event.source}.v1":
        raise ValueError("Event source does not match its NATS subject")
    await asyncio.to_thread(accept, engine, event)
    await message.ack_sync(timeout=10)


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
