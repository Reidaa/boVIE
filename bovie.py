import os


import click
from dotenv import load_dotenv

load_dotenv()

from bovie.businessFrance.Client import Client  # noqa: E402
from bovie.discord.bot import Start  # noqa: E402


@click.command()
@click.option("--token", default=os.environ.get("BOVIE_DISCORD_TOKEN", ""))
def bot(token: str):
    Start(token=token)


@click.command()
@click.option("--limit", default=os.environ.get("BOVIE_OFFER_MAX", "50"))
def pull(limit: int):
    c = Client()
    for o in c.get_new_offers(limit):
        print(
            f"{o.missionTitle} - {o.organizationName} - {o.countryName} - {o.indemnite}e"
        )


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(pull)
    cli.add_command(bot)
    cli()
