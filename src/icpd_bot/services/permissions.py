from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from sqlalchemy import select

from icpd_bot.db.models import GuildReadOnlyRole

if TYPE_CHECKING:
    from icpd_bot.db.session import DatabaseSessionFactory


def member_role_ids(interaction: discord.Interaction) -> set[int]:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return set()
    return {role.id for role in user.roles}


def member_has_role(interaction: discord.Interaction, role_id: int) -> bool:
    return role_id in member_role_ids(interaction)


def member_is_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    return user.guild_permissions.administrator


async def respond_ephemeral(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def interaction_in_home_guild(interaction: discord.Interaction, home_guild_id: int) -> bool:
    guild = interaction.guild
    return guild is not None and guild.id == home_guild_id


async def require_home_guild(interaction: discord.Interaction, home_guild_id: int) -> bool:
    if interaction_in_home_guild(interaction, home_guild_id):
        return True
    await respond_ephemeral(
        interaction,
        f"This bot only works in the configured ICPD server (`{home_guild_id}`).",
    )
    return False


async def has_read_only_access(
    interaction: discord.Interaction,
    *,
    home_guild_id: int,
    council_role_id: int,
    session_factory: "DatabaseSessionFactory",
) -> bool:
    if not interaction_in_home_guild(interaction, home_guild_id):
        return False

    roles = member_role_ids(interaction)
    if council_role_id in roles:
        return True

    async with session_factory.session() as session:
        allowed_roles = set(
            await session.scalars(
                select(GuildReadOnlyRole.role_id).where(GuildReadOnlyRole.guild_id == home_guild_id)
            )
        )
    return bool(roles & allowed_roles)


async def require_read_only_access(
    interaction: discord.Interaction,
    *,
    home_guild_id: int,
    council_role_id: int,
    session_factory: "DatabaseSessionFactory",
) -> bool:
    if not await require_home_guild(interaction, home_guild_id):
        return False
    if await has_read_only_access(
        interaction,
        home_guild_id=home_guild_id,
        council_role_id=council_role_id,
        session_factory=session_factory,
    ):
        return True

    await respond_ephemeral(
        interaction,
        "This command is restricted to the ICPD Council role or a configured read-only access role.",
    )
    return False


async def require_council_access(
    interaction: discord.Interaction,
    *,
    home_guild_id: int,
    council_role_id: int,
) -> bool:
    if not await require_home_guild(interaction, home_guild_id):
        return False
    if member_has_role(interaction, council_role_id):
        return True

    await respond_ephemeral(interaction, "This command is restricted to ICPD Council members.")
    return False
