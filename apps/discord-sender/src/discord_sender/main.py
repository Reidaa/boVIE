import asyncio
import os

import click
import httpx
from cli_common import configure_logging, log_failure
from mysql_common import make_engine
from mysql_common.env import load_env

from discord_sender.delivery import deliver_one


@click.command()
@click.option(
    "--once", is_flag=True, help="Drain currently available deliveries and exit."
)
def main(once: bool):
    """Send queued Discord messages using only Discord database credentials."""
    configure_logging()
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
