from typing import TYPE_CHECKING

import discord
from discord import app_commands

from icpd_bot.integrations.warera import WareraClient
from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.permissions import require_council_access
from icpd_bot.services.warera_sync import WareraSyncService

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


def build_sync_commands(bot: "ICPDBot") -> list[app_commands.Command]:
    @app_commands.command(name="sync_warera_cache", description="Fetch fresh Warera data into the local cache.")
    async def sync_warera_cache(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with WareraClient(
            base_url=bot.settings.warera_api_base_url,
            token=bot.settings.warera_api_token,
        ) as client:
            async with bot.session_factory.session() as session:
                counts = await WareraSyncService(session, client).sync()
                guild_config = await GuildConfigService(session).get_guild_config(bot.settings.discord_guild_id)

        for change in counts.specialization_changes:
            if guild_config and guild_config.alert_channel_id:
                await bot.alert_service.send_to_channel(
                    guild_config.alert_channel_id,
                    change,
                    role_id=guild_config.alert_role_id,
                )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send(
            f"Warera cache synced. Countries: {counts.countries}, regions: {counts.regions}.",
            ephemeral=True,
        )

    return [sync_warera_cache]
