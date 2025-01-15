from typing import List

from rich.console import Console
from rich.table import Table

from src.businessFrance.models import Offer
from src.writer.BaseWriter import BaseWriter


class TerminalWriter(BaseWriter):
    """Handles displaying offers in the terminal"""

    def __init__(self):
        self.console = Console()

    def write(self, offer: Offer) -> bool:
        return super().write_many(offer)

    def write_many(self, offers: List[Offer]):
        """Display offers in a formatted table"""
        table = Table(title="Latest VIE/VIA Offers")

        table.add_column("Title", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Location", style="green")
        table.add_column("Start Date", style="blue")

        for offer in offers:
            table.add_row(
                offer.missionTitle.strip(),
                offer.organizationName.strip(),
                f"{offer.cityName.strip()}, {offer.countryName.strip()}",
                offer.missionStartDate,
            )

        self.console.print(table)
