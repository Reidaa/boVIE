import hikari
import miru


class MyView(miru.View):
    @miru.button(label="Rock", emoji="\N{ROCK}", style=hikari.ButtonStyle.PRIMARY)
    async def rock_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await ctx.respond("Paper!")

    @miru.button(label="Paper", emoji="\N{SCROLL}", style=hikari.ButtonStyle.PRIMARY)
    async def paper_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await ctx.respond("Scissors!")

    @miru.button(
        label="Scissors",
        emoji="\N{BLACK SCISSORS}",
        style=hikari.ButtonStyle.PRIMARY,
    )
    async def scissors_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        await ctx.respond("Rock!")

    @miru.button(
        emoji="\N{BLACK SQUARE FOR STOP}", style=hikari.ButtonStyle.DANGER, row=1
    )
    async def stop_button(self, ctx: miru.ViewContext, button: miru.Button) -> None:
        self.stop()  # Stop listening for interactions
