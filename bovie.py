import os


import click
from dotenv import load_dotenv

from bovie.businessFrance.Service import Service
from bovie.discord.bot import Start
from bovie.discord.Config import Config

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
    c = Service()
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
