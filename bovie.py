import os


import click
from dotenv import load_dotenv

load_dotenv()

from bovie.businessFrance.Client import Client  # noqa: E402
from bovie.businessFrance.OfferRepository import SearchParameters  # noqa: E402
from bovie.discord.bot import Start  # noqa: E402


@click.command()
@click.option("--limit", default=os.environ.get("BOVIE_OFFER_MAX", "10"))
def offers(limit: int):
    c = Client()

    params = SearchParameters(limit=limit)
    offers = c.offers.search(params)
    for i in offers:
        offer = c.offers.findOne(i.id)
        if offer.countryName not in ["JAPON", "ETATS-UNIS", "SUISSE", "AUSTRALIE"]:
            continue
        print(
            f"{offer.missionTitle} - {offer.organizationName} - {offer.countryName} - {offer.indemnite}e"
        )


@click.command()
@click.option("--token", default=os.environ.get("BOVIE_DISCORD_TOKEN", ""))
def bot(token: str):
    Start(token=token)


@click.command()
def version():
    pass


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(offers)
    cli.add_command(bot)
    cli.add_command(version)
    cli()
