from typing import TYPE_CHECKING

import discord
from discord import app_commands

from icpd_bot.integrations.warera import WareraClient
from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.permissions import member_is_admin
from icpd_bot.services.warera_sync import WareraSyncService

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


def build_sync_commands(bot: "ICPDBot") -> list[app_commands.Command]:
    @app_commands.command(name="sync_warera_cache", description="Fetch fresh Warera data into the local cache.")
    async def sync_warera_cache(interaction: discord.Interaction) -> None:
        if not member_is_admin(interaction):
            await interaction.response.send_message(
                "This command requires Discord administrator permission.",
                ephemeral=True,
            )
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
                await bot.alert_service.send_to_channel(guild_config.alert_channel_id, change)
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send(
            f"Warera cache synced. Countries: {counts.countries}, regions: {counts.regions}.",
            ephemeral=True,
        )

    return [sync_warera_cache]
