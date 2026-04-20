from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import GuildConfig, GuildReadOnlyRole


class GuildConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_guild_config(
        self,
        *,
        guild_id: int,
        council_role_id: int,
        refresh_interval_minutes: int,
    ) -> GuildConfig:
        existing = await self.session.scalar(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        if existing is not None:
            return existing

        config = GuildConfig(
            guild_id=guild_id,
            council_role_id=council_role_id,
            default_refresh_interval_minutes=refresh_interval_minutes,
        )
        self.session.add(config)
        return config

    async def get_guild_config(self, guild_id: int) -> GuildConfig | None:
        return await self.session.scalar(select(GuildConfig).where(GuildConfig.guild_id == guild_id))

    async def set_alert_channel(self, guild_id: int, channel_id: int | None) -> GuildConfig:
        config = await self.get_guild_config(guild_id)
        if config is None:
            raise ValueError(f"Guild config {guild_id} does not exist.")
        config.alert_channel_id = channel_id
        return config

    async def list_read_only_roles(self, guild_id: int) -> list[GuildReadOnlyRole]:
        return list(
            await self.session.scalars(
                select(GuildReadOnlyRole)
                .where(GuildReadOnlyRole.guild_id == guild_id)
                .order_by(GuildReadOnlyRole.role_id)
            )
        )

    async def add_read_only_role(self, guild_id: int, role_id: int) -> GuildReadOnlyRole:
        record = await self.session.get(GuildReadOnlyRole, {"guild_id": guild_id, "role_id": role_id})
        if record is not None:
            return record

        record = GuildReadOnlyRole(guild_id=guild_id, role_id=role_id)
        self.session.add(record)
        return record

    async def remove_read_only_role(self, guild_id: int, role_id: int) -> bool:
        record = await self.session.get(GuildReadOnlyRole, {"guild_id": guild_id, "role_id": role_id})
        if record is None:
            return False
        await self.session.delete(record)
        return True
