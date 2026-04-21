from __future__ import annotations

import discord


class AlertService:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot

    async def send_to_channel(self, channel_id: int | None, message: str, *, role_id: int | None = None) -> bool:
        if channel_id is None:
            return False
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return False
        if isinstance(channel, discord.TextChannel):
            settings = getattr(self.bot, "settings", None)
            if settings is not None and channel.guild.id != settings.discord_guild_id:
                return False
            content = f"<@&{role_id}> {message}" if role_id is not None else message
            await channel.send(content, allowed_mentions=discord.AllowedMentions(roles=True))
            return True
        return False
