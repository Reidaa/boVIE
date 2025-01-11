import asyncio
import logging

import hikari

from bovie.businessFrance.Service import Service
from bovie.discord.Config import Config
from bovie.discord.embeds.offer import OfferEmbed

logger = logging.getLogger("bovie.discord.bot")


async def loop(bot: hikari.GatewayBot, cfg: Config, cooldown: int = 60):
    logger.info("Starting loop")

    client = Service()
    channel = await bot.rest.fetch_channel(cfg.channel_ID)

    while True:
        logger.info("Waking Up.")
        new_offers = client.get_new_offers(limit=cfg.max_pull)
        for o in new_offers:
            embed = OfferEmbed(o)
            logger.info("sending message")
            try:
                await channel.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Error sending message: {0}".format(e))
                # If there's an error, wait a bit before retrying
                await asyncio.sleep(5)
            logger.info("sending message. Done")

        logger.info("Sleeping for {0} seconds. Zzz".format(cooldown))
        await asyncio.sleep(cooldown)


def Start(cfg: Config):
    bot = hikari.GatewayBot(token=cfg.token)

    # Start the background task when the bot starts
    @bot.listen(hikari.StartedEvent)
    async def on_ready(event):
        # Create the background task
        asyncio.create_task(loop(bot, cfg))

    activity = hikari.Activity(
        name="David-ing till 2025", type=hikari.ActivityType.CUSTOM
    )
    bot.run(activity=activity)
