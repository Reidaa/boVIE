import logging

import nextcord
from nextcord.ext import commands

from bovie.discord.Config import Config
from bovie.discord.cogs.vie import VIE

logger = logging.getLogger("bovie.discord.bot")


# async def loop(bot: hikari.GatewayBot, cfg: Config, cooldown: int = 60):
#     logger.info("Starting loop")

#     client = Service()
#     channel = await bot.rest.fetch_channel(cfg.channel_ID)

#     p = SearchParameters(
#         limit=cfg.max_pull,
#         specializationsIds=[
#             Specializations.INFORMATION_SYSTEMS.value,
#             Specializations.SCIENTIFIC_AND_INDUSTRIAL_COMPUTING.value,
#         ],
#         gerographicZones=[
#             Regions.ASIA_PACIFIC.value,
#             Regions.NORTH_AMERICA.value,
#             Regions.SOUTH_AMERICA.value,
#             Regions.WESTERN_EUROPE.value,
#         ],
#     )

#     while True:
#         logger.info("Waking Up.")
#         new_offers = client.get_new_offers(p)
#         for o in new_offers:
#             embed = OfferEmbed(o)
#             logger.info("sending message")
#             try:
#                 await channel.send(embed=embed)
#                 await asyncio.sleep(0.5)
#             except Exception as e:
#                 logger.error("Error sending message: {0}".format(e))
#                 # If there's an error, wait a bit before retrying
#                 await asyncio.sleep(5)
#             logger.info("sending message. Done")

#         logger.info("Sleeping for {0} seconds. Zzz".format(cooldown))
#         await asyncio.sleep(cooldown)


def Start(cfg: Config):
    intents = nextcord.Intents.default()
    # intents.members = True
    # intents.message_content = True

    bot = commands.Bot(intents=intents)

    @bot.group()
    async def cool(ctx):
        """Says if a user is cool.

        In reality this just checks if a subcommand is being invoked.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(f"No, {ctx.subcommand_passed} is not cool")

    @cool.command(name="bot")
    async def _bot(ctx):
        """Is the bot cool?"""
        await ctx.send("Yes, the bot is cool.")

    bot.add_cog(VIE(bot, cfg))

    bot.run(token=cfg.token)
