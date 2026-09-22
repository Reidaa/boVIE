import asyncio

import click
from job_contracts import OfferDiscovered
from job_database import make_engine
from job_database.env import load_env
from job_database.queue import claim, finish, retry_later
from job_messaging import connect
from job_runtime import configure_logging, log_failure
from source_store import Outbox
from sqlalchemy.engine import Engine


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


@click.command()
@click.option("--source", required=True, type=click.Choice(["business_france", "wttj"]))
@click.option("--once", is_flag=True, help="Drain currently available work and exit.")
def main(source: str, once: bool):
    """Publish this source's committed outbox to JetStream."""
    configure_logging()
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
