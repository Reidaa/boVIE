import asyncio

import arc
import hikari
import miru

from bovie.businessFrance.generated.models import Offer
from bovie.discord.embeds.offer import OfferEmbed
from bovie.discord.views.example import MyView

offer = Offer(
    id=218211,
    organizationName="SIVECO GROUP",
    missionTitle="CONSULTANT(E) FORMATEUR GMAO JUNIOR F/H",
    missionDuration=12,
    viewCounter=3635,
    candidateCounter=103,
    missionType="VIE",
    missionTypeEn="VIE",
    organizationPresentation="Siveco Goup est le spécialiste de la GMAO depuis 1986, nous sommes présent en France et à l’international. Concepteur et éditeur des solutions Coswin, l’intégration est faite par nos équipes.\r\nNotre siège social est basé en Ile de France, nos centres de R&D sur Montpellier et Catane.\r\nNotre réseau international de distribution est constitué de 8 Filiales (Angleterre, Belgique, Brésil, Cote d’Ivoire, Italie, Suisse et Tunisie), 2 sociétés affiliées (Grèce, Chine) et 20 distributeurs.\r\nNous avons plus 1800 sites clients dans tous les secteurs d’activité : Industrie, agro-alimentaire, pharmacie, énergie, Tertiaire, collectivités, gestion eau & déchets, transport & logistique, santé, distribution, défense ...\r\nNotre philosophie Produit : \r\n-\tUne version majeure tous les 15 mois,\r\n-\tPas de rupture entre versions majeures,\r\n-\tFonctionne sur base de données : Oracle et Microsoft SQL server,\r\n-\tApplication web accessible via un navigateur internet,\r\n-\tUn logiciel personnalisable,\r\n-\tUn logiciel multilingue.\r\n",
    organizationUrlImage="http://mull.jpeg",
    organizationPathImage="",
    pathImage=None,
    activitySectorN1="TECHNOLOGIES DE L'INFORMATION ET DES TELECOMMUNICATIONS",
    activitySectorN2=None,
    activitySectorN3=None,
    activitySectorN1Id=100011,
    ca="8334",
    effectif=80,
    organizationCountryCounter="30",
    organizationExpertise=None,
    cityAffectationId=2199,
    cityName="FRIBOURG                                ",
    cityNameEn="FRIBOURG                                ",
    activitySectorOfferId=11,
    levelStudyIds=None,
    specializations=None,
    missionDescription="Présentation de la société :\r\nSiveco Group est éditeur de logiciels de gestion de maintenance (GMAO) depuis 1986 et se positionne aujourd’hui comme un acteur incontournable en France et à l’international. \r\nAvec plus de 1800 sites clients dans tous les secteurs d’activités et plusieurs dizaines de milliers d’utilisateurs dans le monde, Siveco Group garantit une expertise métier mise en œuvre dans les plus grandes entreprises. \r\nAujourd'hui, nos solutions logicielles Coswin aident les entreprises à relever les défis liés aux contextes d'Industrie du Futur et de ville & bâtiments intelligents. \r\n\r\nNotre filiale Suisse a été créée en novembre 2020. Afin de se développer, nous sommes à la recherche d’un candidat motivé.\r\nIl sera formé et accompagne par nos équipes du siège social et notre centre technique à Montpellier. Nos collaborateurs développeurs, analyses, consultants seront à tout moment présent afin de vous intégrer pleinement dans cette mission.\r\n\r\nVos missions : \r\nVous intègrerez Siveco Group en tant que Consultant(e) Formateur GMAO Junior. \r\nAprès avoir suivi une formation interne à notre gamme logicielle Coswin 8i, vous aurez pour principales responsabilités :\r\nAnalyse et préparation\r\n- Rencontrer le client pour déterminer ses besoins spécifiques\r\n- Concevoir des programmes de formation sur mesure adaptés aux objectifs de l'entreprise\r\n\r\nAnimation et formation\r\n- Animer les sessions de formation de manière dynamique et interactive\r\n- Transmettre son savoir et ses compétences aux participants\r\n- Répondre aux questions et s'adapter à son auditoire\r\n- Utiliser diverses techniques pédagogiques pour faciliter l'apprentissage\r\n\r\nÉvaluation et suivi\r\n- Évaluer la bonne compréhension et l'acquisition des compétences par les participants\r\n- Effectuer un suivi post-formation pour vérifier la mise en application\r\n\r\nDéveloppement de l'activité  \r\n- Concevoir des offres de formation adaptées aux besoins du marché\r\n",
    creationDate="2024-09-30T16:04:04.353",
    missionStartDate="2025-04-01T00:00:00",
    missionEndDate="2026-04-01T00:00:00",
    startBroadcastDate="2025-01-09T00:00:00",
    durationBroadcast=210,
    organizationId=18031,
    missionProfile="Cette offre est faite pour vous si : \r\n- Vous êtes issu d'une formation Bac +5 et plus, de formation maintenance, production ou équivalent,\r\n- Vous disposez d'une première expérience professionnelle ou avez effectué des stages en milieu industriel et/ou tertiaire,\r\n- Vous parlez Anglais et l'Allemand est souhaité,\r\n- Vous avez de bonnes capacités orales et rédactionnelles,\r\n- Vous avez le sens du relationnel.\r\n",
    countryId="131",
    countryName="SUISSE",
    countryNameEn="SWITZERLAND",
    reference="VIE219211",
    contactName=" ",
    indemnite=3968,
    idMotifDesactivationOffre=0,
    contactEmail="Business France",
    cityAffectation="FRIBOURG                                ",
    idNomenclatureSecteur=None,
)
offerEmbed = OfferEmbed(offer=offer)


async def loop(bot: hikari.GatewayBot, cooldown: int = 10):
    channel = await bot.rest.fetch_channel(1327435046029627463)

    # embed = hikari.Embed(
    #     title="Periodic Update",
    #     description="This is a periodic update message",
    #     color=hikari.Color.from_hex_code("#d65008"),
    # )

    while True:
        try:
            await channel.send(embed=offerEmbed)
            await asyncio.sleep(cooldown)
        except Exception as e:
            print(f"Error sending message: {e}")
            # If there's an error, wait a bit before retrying
            await asyncio.sleep(5)


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
        return await ctx.respond(f"Hey {user.mention}")

    # Start the background task when the bot starts
    @bot.listen(hikari.StartedEvent)
    async def on_ready(event):
        # Create the background task
        asyncio.create_task(loop(bot))

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
