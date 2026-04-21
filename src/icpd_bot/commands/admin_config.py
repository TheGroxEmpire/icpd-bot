from typing import TYPE_CHECKING

import discord
from discord import app_commands

from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.permissions import require_council_access

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


def build_admin_config_commands(bot: "ICPDBot") -> list[app_commands.Command]:
    @app_commands.command(
        name="set_alert_channel",
        description="Set the shared alert channel for recommendation and specialization alerts.",
    )
    async def set_alert_channel(
        interaction: discord.Interaction,
        channel_id: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        try:
            normalized_channel_id = int(channel_id)
        except ValueError:
            await interaction.response.send_message(
                "Channel ID must be a numeric Discord channel ID.",
                ephemeral=True,
            )
            return

        try:
            channel = await bot.fetch_channel(normalized_channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            await interaction.response.send_message(
                "I could not access that channel. Make sure the bot is invited there and can view it.",
                ephemeral=True,
            )
            return

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "The alert channel must be a text channel.",
                ephemeral=True,
            )
            return
        if channel.guild.id != bot.settings.discord_guild_id:
            await interaction.response.send_message(
                "The alert channel must be inside the configured ICPD server.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            service = GuildConfigService(session)
            await service.set_alert_channel(bot.settings.discord_guild_id, normalized_channel_id)

        await interaction.response.send_message(
            f"Shared alert channel set to `{normalized_channel_id}` ({channel.name}).",
            ephemeral=True,
        )

    @app_commands.command(
        name="clear_alert_channel",
        description="Clear the shared alert channel setting.",
    )
    async def clear_alert_channel(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            service = GuildConfigService(session)
            await service.set_alert_channel(bot.settings.discord_guild_id, None)

        await interaction.response.send_message(
            "Shared alert channel cleared.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_alert_role",
        description="Set a role to mention whenever the bot posts an alert.",
    )
    async def set_alert_role(interaction: discord.Interaction, role_id: str) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        try:
            normalized_role_id = int(role_id)
        except ValueError:
            await interaction.response.send_message(
                "Role ID must be a numeric Discord role ID.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        role = guild.get_role(normalized_role_id) if guild is not None else None
        if role is None:
            await interaction.response.send_message(
                "I could not find that role in the configured ICPD server.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            service = GuildConfigService(session)
            await service.set_alert_role(bot.settings.discord_guild_id, normalized_role_id)

        await interaction.response.send_message(
            f"Alert role set to {role.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="clear_alert_role",
        description="Stop mentioning a role when posting alerts.",
    )
    async def clear_alert_role(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            service = GuildConfigService(session)
            await service.set_alert_role(bot.settings.discord_guild_id, None)

        await interaction.response.send_message(
            "Alert role cleared.",
            ephemeral=True,
        )

    return [set_alert_channel, clear_alert_channel, set_alert_role, clear_alert_role]
