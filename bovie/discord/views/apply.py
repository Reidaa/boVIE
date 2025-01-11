import miru


class ApplyButton(miru.LinkButton):
    def __init__(self, offerURL: str):
        # super().__init__(style=hikari.ButtonStyle.PRIMARY, label="Apply")
        super().__init__(url=offerURL, label="Apply")
        self.value = True
        self.offerURL = offerURL

    async def callback(self, ctx: miru.ViewContext):
        return await super().callback(ctx)
