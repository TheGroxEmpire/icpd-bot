from typing import TYPE_CHECKING

import discord
from discord import app_commands
from sqlalchemy import select

from icpd_bot.db.models import ActiveRegionList, GuildConfig, SyncState

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


def build_status_command(bot: "ICPDBot") -> app_commands.Command:
    @app_commands.command(name="bot_status", description="Show bot configuration and cache status.")
    async def bot_status(interaction: discord.Interaction) -> None:
        async with bot.session_factory.session() as session:
            sync_state = await session.get(SyncState, "warera_sync")
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)
            active_lists = list(
                await session.scalars(
                    select(ActiveRegionList).where(ActiveRegionList.active.is_(True))
                )
            )

        embed = discord.Embed(title="ICPD Bot Status")
        embed.add_field(name="Guild ID", value=str(bot.settings.discord_guild_id), inline=False)
        embed.add_field(
            name="Alert Channel",
            value=(
                str(guild_config.alert_channel_id)
                if guild_config and guild_config.alert_channel_id
                else "Not configured"
            ),
            inline=False,
        )
        embed.add_field(
            name="Refresh Interval",
            value=f"{bot.settings.recommended_region_refresh_minutes} minutes",
            inline=False,
        )
        embed.add_field(
            name="Warera Sync Interval",
            value=f"{bot.settings.sync_interval_seconds} seconds",
            inline=False,
        )
        embed.add_field(name="Managed Embeds", value=str(len(active_lists)), inline=False)
        embed.add_field(
            name="Last Sync Success",
            value=sync_state.last_success_at.isoformat() if sync_state and sync_state.last_success_at else "Never",
            inline=False,
        )
        if sync_state and sync_state.row_counts:
            embed.add_field(name="Last Sync Counts", value=sync_state.row_counts, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return bot_status
