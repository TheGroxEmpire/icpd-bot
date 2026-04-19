from __future__ import annotations

import discord


class AlertService:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot

    async def send_to_channel(self, channel_id: int | None, message: str) -> bool:
        if channel_id is None:
            return False
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return False
        if isinstance(channel, discord.TextChannel):
            await channel.send(message)
            return True
        return False
