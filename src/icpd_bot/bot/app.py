import asyncio
import logging

import discord
from discord.ext import commands, tasks
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.commands.admin_config import build_admin_config_commands
from icpd_bot.commands.country_management import build_country_management_commands
from icpd_bot.commands.recommendations import build_recommendation_commands
from icpd_bot.commands.status import build_status_command
from icpd_bot.commands.sync import build_sync_commands
from icpd_bot.config.settings import Settings, get_settings
from icpd_bot.db.session import DatabaseSessionFactory
from icpd_bot.integrations.warera import WareraClient
from icpd_bot.services.alerts import AlertService
from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.logging import configure_logging
from icpd_bot.services.managed_embeds import ManagedEmbedService
from icpd_bot.services.recommendations import RecommendationService
from icpd_bot.services.warera_sync import WareraSyncService
from icpd_bot.views.recommended_regions import build_recommended_regions_embed


class ICPDBot(commands.Bot):
    def __init__(self, settings: Settings, session_factory: DatabaseSessionFactory) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents, application_id=settings.discord_application_id)
        self.settings = settings
        self.session_factory = session_factory
        self.alert_service = AlertService(self)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.settings.discord_guild_id)
        commands = [
            build_status_command(self),
            *build_admin_config_commands(self),
            *build_country_management_commands(self),
            *build_sync_commands(self),
            *build_recommendation_commands(self),
        ]
        self.tree.clear_commands(guild=None)
        self.tree.clear_commands(guild=guild)
        for command in commands:
            self.tree.add_command(command, guild=guild)
        await self.tree.sync()
        await self.tree.sync(guild=guild)

        async with self.session_factory.session() as session:
            service = GuildConfigService(session)
            await service.ensure_guild_config(
                guild_id=self.settings.discord_guild_id,
                council_role_id=self.settings.council_role_id,
                refresh_interval_minutes=self.settings.recommended_region_refresh_minutes,
            )
        self.refresh_managed_embeds_loop.start()
        self.periodic_sync_loop.change_interval(seconds=self.settings.sync_interval_seconds)
        self.periodic_sync_loop.start()

    async def on_ready(self) -> None:
        logging.getLogger(__name__).info("Discord bot connected as %s", self.user)

    async def close(self) -> None:
        if self.refresh_managed_embeds_loop.is_running():
            self.refresh_managed_embeds_loop.cancel()
        if self.periodic_sync_loop.is_running():
            self.periodic_sync_loop.cancel()
        await self.session_factory.engine.dispose()
        await super().close()

    @staticmethod
    def managed_embed_service_factory(session: AsyncSession) -> ManagedEmbedService:
        return ManagedEmbedService(session)

    async def refresh_due_embeds(self, *, force_all: bool = False) -> int:
        refreshed = 0
        async with self.session_factory.session() as session:
            embed_service = ManagedEmbedService(session)
            records = await (embed_service.list_active() if force_all else embed_service.due_active_lists())
            if not records:
                return 0
            entries = await RecommendationService(session).build_recommendations(self.settings.discord_guild_id)
            embed = build_recommended_regions_embed(entries)
            for record in records:
                try:
                    channel = await self.fetch_channel(record.channel_id)
                    if not isinstance(channel, discord.TextChannel):
                        continue
                    message = await channel.fetch_message(record.message_id)
                    await message.edit(embed=embed)
                    await embed_service.mark_refreshed(record.message_id)
                    refreshed += 1
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    record.active = False
        return refreshed

    async def run_periodic_sync(self) -> None:
        async with WareraClient(
            base_url=self.settings.warera_api_base_url,
            token=self.settings.warera_api_token,
        ) as client:
            async with self.session_factory.session() as session:
                counts = await WareraSyncService(session, client).sync()
                guild_config = await GuildConfigService(session).get_guild_config(self.settings.discord_guild_id)
        if guild_config and guild_config.alert_channel_id:
            for change in counts.specialization_changes:
                await self.alert_service.send_to_channel(guild_config.alert_channel_id, change)
        await self.refresh_due_embeds(force_all=True)

    @tasks.loop(seconds=60)
    async def refresh_managed_embeds_loop(self) -> None:
        await self.refresh_due_embeds(force_all=False)

    @tasks.loop(seconds=300)
    async def periodic_sync_loop(self) -> None:
        await self.run_periodic_sync()

    @refresh_managed_embeds_loop.before_loop
    async def before_refresh_managed_embeds_loop(self) -> None:
        await self.wait_until_ready()

    @periodic_sync_loop.before_loop
    async def before_periodic_sync_loop(self) -> None:
        await self.wait_until_ready()


def create_bot() -> ICPDBot:
    settings = get_settings()
    configure_logging(settings.log_level)
    session_factory = DatabaseSessionFactory(settings.database_url)
    return ICPDBot(settings=settings, session_factory=session_factory)


def run() -> None:
    bot = create_bot()
    asyncio.run(bot.start(bot.settings.discord_token))
