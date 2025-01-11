import asyncio

import hikari

from bovie.businessFrance.Client import Client
from bovie.discord.embeds.offer import OfferEmbed
import logging

logger = logging.getLogger("bovie.discord.bot")


async def loop(bot: hikari.GatewayBot, cooldown: int = 60):
    logger.info("Starting loop")

    client = Client()
    channel = await bot.rest.fetch_channel(1327435046029627463)

    while True:
        try:
            new_offers = client.get_new_offers(limit=50)
            for o in new_offers:
                embed = OfferEmbed(o)
                await channel.send(embed=embed)
            logger.info("Sleeping for {0} seconds. Zzz".format(cooldown))
            await asyncio.sleep(cooldown)
        except Exception as e:
            print(f"Error sending message: {e}")
            # If there's an error, wait a bit before retrying
            await asyncio.sleep(5)


def Start(token: str):
    bot = hikari.GatewayBot(token=token)

    # Start the background task when the bot starts
    @bot.listen(hikari.StartedEvent)
    async def on_ready(event):
        # Create the background task
        asyncio.create_task(loop(bot))

    activity = hikari.Activity(
        name="David-ing till 2025", type=hikari.ActivityType.CUSTOM
    )
    bot.run(activity=activity)
