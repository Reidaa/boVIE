from pprint import pprint

import click
from dotenv import load_dotenv

load_dotenv()

from bovie.businessFrance.BFClient import BFClient
from bovie.businessFrance.OfferRepository import SearchParameters


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
            f"{offer["missionTitle"]} - {offer["organizationName"]} - {offer["countryName"]} - {offer["indemnite"]}e"
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
            f"{offer["missionTitle"]} - {offer["organizationName"]} - {offer["countryName"]} - {offer["indemnite"]}e"
        )


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(offers)
    cli()
