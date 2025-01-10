import hikari
import miru
import arc

from bovie.discord.views.example import MyView


def Start(token: str):
    bot = hikari.GatewayBot(token=token)
    arcClient = arc.GatewayClient(bot)
    miruClient = miru.Client.from_arc(arcClient)

    @bot.listen()
    async def ping(event: hikari.GuildMessageCreateEvent) -> None:
        """If a non-bot user mentions your bot, respond with 'Pong!'."""

        # Do not respond to bots nor webhooks pinging us, only user accounts
        if not event.is_human:
            return

        me = bot.get_me()

        if me.id in event.message.user_mentions_ids:
            view = MyView()
            await event.message.respond("Pong!", components=view)
            miruClient.start_view(view)

    @arcClient.include
    @arc.slash_command("hi", "Say hi!")
    async def pingg(
        ctx: arc.GatewayContext,
        user: arc.Option[hikari.User, arc.UserParams("The user to say hi to.")],
    ) -> None:
        await ctx.reponsd(f"Hey {user.mention}")

    activity = hikari.Activity(
        name="Davied-ing till 2025", type=hikari.ActivityType.CUSTOM
    )
    bot.run(activity=activity)


# async def ping():
#     """If a non-bot user mentions your bot, respond with 'Pong!'."""

#     # Do not respond to bots nor webhooks pinging us, only user accounts
#     if not event.is_human:
#         return

#     me = bot.get_me()

#     if me.id in event.message.user_mentions_ids:
#         await event.message.respond("Pong!")
