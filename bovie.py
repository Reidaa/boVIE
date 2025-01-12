import os


import click
from dotenv import load_dotenv

from bovie.businessFrance.Service import Service as BFService
from bovie.discord.bot import Start
from bovie.discord.Config import Config
from bovie.businessFrance.models import SearchParameters
from bovie.businessFrance.enum import Specializations, Regions

load_dotenv()


@click.command()
@click.option("--token", default=os.environ.get("BOVIE_DISCORD_TOKEN", ""))
@click.option("--limit", default=os.environ.get("BOVIE_OFFER_MAX", "50"))
@click.option("--channel", default=os.environ.get("BOVIE_DISCORD_CHANNEL", ""))
def bot(token: str, limit: int, channel: str):
    cfg = Config(token=token, max_pull=limit, channel_ID=channel)
    Start(cfg)


@click.command()
@click.option("--limit", default=os.environ.get("BOVIE_OFFER_MAX", "1"))
def pull(limit: int):
    import logging

    logging.basicConfig(level=logging.INFO)
    c = BFService()
    p = SearchParameters(
        limit=limit,
        specializationsIds=[
            Specializations.INFORMATION_SYSTEMS.value,
            Specializations.SCIENTIFIC_AND_INDUSTRIAL_COMPUTING.value,
        ],
        gerographicZones=[
            Regions.ASIA_PACIFIC.value,
            Regions.NORTH_AMERICA.value,
            Regions.SOUTH_AMERICA.value,
            Regions.WESTERN_EUROPE.value,
        ],
    )

    for o in c.get_new_offers(p):
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
