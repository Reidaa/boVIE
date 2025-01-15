import asyncio
import logging

from nextcord.ext import commands, tasks
from nextcord.client import Client

from bovie.businessFrance.enum import Regions, Specializations
from bovie.businessFrance.models import SearchParameters
from bovie.businessFrance.Service import Service
from bovie.discord.Config import Config
from bovie.discord.embeds.offer import OfferEmbed

logger = logging.getLogger("bovie.discord.bot.vie")


class VIE(commands.Cog):
    def __init__(self, bot: Client, cfg: Config):
        super().__init__()
        self.bot = bot
        self.cfg = cfg
        self.client = Service()
        self.channel_id = int(cfg.channel_ID)

        self.params = SearchParameters(
            limit=self.cfg.max_pull,
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

        print(self.channel_id)

        self.loop.start()

    def cog_unload(self):
        self.loop.cancel()

    @tasks.loop(seconds=10.0)
    async def loop(self):
        print("Loopppiiing")
        new_offers = self.client.get_new_offers(self.params)

        channel = self.bot.get_channel(id=int(self.channel_id))
        if channel is None:
            print("weird")
            return

        for o in new_offers:
            embed = OfferEmbed(o)
            print("sending message")
            try:
                await channel.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                print("Error sending message: {0}".format(e))
                # If there's an error, wait a bit before retrying
                await asyncio.sleep(5)
            print("sending message. Done")

    @loop.before_loop
    async def before_loop(self):
        print("Waking Up ...")
        await self.bot.wait_until_ready()
