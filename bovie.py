import os

import click
from dotenv import load_dotenv

load_dotenv()

from bovie.businessFrance.BFClient import BFClient  # noqa: E402
from bovie.businessFrance.OfferRepository import SearchParameters  # noqa: E402


def main():
    c = BFClient()

    params = SearchParameters(limit=2000)
    offers = c.offers.search(params)
    for i in offers:
        id = i["id"]
        offer = c.offers.findOne(id)
        if offer["countryName"] not in ["JAPON", "ETATS-UNIS", "SUISSE", "AUSTRALIE"]:
            continue
        print(
            f"{offer['missionTitle']} - {offer['organizationName']} - {offer['countryName']} - {offer['indemnite']}e"
        )


@click.command()
@click.option("--limit", default=10)
def offers(limit: int):
    c = BFClient()

    params = SearchParameters(limit=limit)
    offers = c.offers.search(params)
    for i in offers:
        id = i["id"]
        offer = c.offers.findOne(id)
        if offer["countryName"] not in ["JAPON", "ETATS-UNIS", "SUISSE", "AUSTRALIE"]:
            continue
        print(
            f"{offer['missionTitle']} - {offer['organizationName']} - {offer['countryName']} - {offer['indemnite']}e"
        )


@click.command()
@click.option("--token", default=os.environ.get("DISCORD_TOKEN", ""))
def bot(token: str):
    pass


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
