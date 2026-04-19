from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import ActiveRegionList


class ManagedEmbedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_active_list(
        self,
        *,
        guild_id: int,
        channel_id: int,
        message_id: int,
        refresh_interval_minutes: int,
    ) -> ActiveRegionList:
        record = ActiveRegionList(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            refresh_interval_minutes=refresh_interval_minutes,
            active=True,
            last_refresh_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        return record

    async def get_active_list(self, message_id: int) -> ActiveRegionList | None:
        return await self.session.get(ActiveRegionList, message_id)

    async def deactivate(self, message_id: int) -> bool:
        record = await self.get_active_list(message_id)
        if record is None:
            return False
        record.active = False
        return True

    async def mark_refreshed(self, message_id: int) -> None:
        record = await self.get_active_list(message_id)
        if record is not None:
            record.last_refresh_at = datetime.now(timezone.utc)

    async def list_active(self) -> list[ActiveRegionList]:
        return list(
            await self.session.scalars(
                select(ActiveRegionList).where(ActiveRegionList.active.is_(True))
            )
        )

    async def due_active_lists(self) -> list[ActiveRegionList]:
        now = datetime.now(timezone.utc)
        active_records = await self.list_active()
        return [
            record
            for record in active_records
            if record.last_refresh_at is None
            or record.last_refresh_at + timedelta(minutes=record.refresh_interval_minutes) <= now
        ]
