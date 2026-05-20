import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord import app_commands

from icpd_bot.db.models import SyncState
from icpd_bot.integrations.warera import WareraClient
from icpd_bot.integrations.warera.client import WareraApiError
from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.permissions import require_council_access
from icpd_bot.services.warera_sync import WareraSyncService

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


logger = logging.getLogger(__name__)

SYNC_JOB_NAME = "warera_sync"


def build_sync_commands(bot: "ICPDBot") -> list[app_commands.Command[Any, ..., None]]:
    @app_commands.command(
        name="sync_warera_cache",
        description="Fetch fresh Warera data into the local cache.",
    )
    async def sync_warera_cache(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.edit_original_response(content="Warera cache sync started.")

        try:
            async with WareraClient(
                base_url=bot.settings.warera_api_base_url,
                token=bot.settings.warera_api_token,
            ) as client:
                async with bot.session_factory.session() as session:
                    counts = await WareraSyncService(session, client).sync()
                    guild_config = await GuildConfigService(session).get_guild_config(
                        bot.settings.discord_guild_id
                    )
        except Exception as exc:
            logger.exception("Manual Warera cache sync failed.")
            await _record_sync_failure(bot, exc)
            await interaction.followup.send(
                f"Warera cache sync failed. {_sync_failure_summary(exc)}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Warera cache synced. Countries: {counts.countries}, regions: {counts.regions}.",
            ephemeral=True,
        )

        try:
            alert_messages = [
                *counts.specialization_changes,
                *counts.proxy_active_population_warnings,
            ]
            sent_alerts = 0
            if guild_config and guild_config.alert_channel_id:
                for change in alert_messages:
                    if await bot.alert_service.send_to_channel(
                        guild_config.alert_channel_id,
                        change,
                        role_id=guild_config.alert_role_id,
                    ):
                        sent_alerts += 1
            refreshed = await bot.refresh_due_embeds(force_all=True)
        except Exception:
            logger.exception("Post-sync tasks failed after manual Warera cache sync.")
            await interaction.followup.send(
                "Warera cache synced, but post-sync alerts or managed embed refresh failed. "
                "Check the bot logs for details.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Post-sync complete. Alerts sent: {sent_alerts}, "
            f"managed embeds refreshed: {refreshed}.",
            ephemeral=True,
        )

    return [sync_warera_cache]


async def _record_sync_failure(bot: "ICPDBot", exc: Exception) -> None:
    try:
        async with bot.session_factory.session() as session:
            sync_state = await session.get(SyncState, SYNC_JOB_NAME)
            if sync_state is None:
                sync_state = SyncState(job_name=SYNC_JOB_NAME)
                session.add(sync_state)
            sync_state.last_failure_at = datetime.now(UTC)
            sync_state.last_error = _clip_detail(f"{type(exc).__name__}: {exc}", limit=1000)
    except Exception:
        logger.exception("Failed to record Warera sync failure state.")


def _sync_failure_summary(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Warera API returned HTTP {exc.response.status_code}."
    if isinstance(exc, httpx.TimeoutException):
        return "Warera API request timed out."
    if isinstance(exc, httpx.RequestError):
        return f"Warera API request failed ({type(exc).__name__})."
    if isinstance(exc, WareraApiError):
        return f"Warera API response was invalid: {_clip_detail(str(exc))}"
    return f"{type(exc).__name__}. Check the bot logs for details."


def _clip_detail(value: str, *, limit: int = 240) -> str:
    detail = " ".join(value.split())
    if len(detail) <= limit:
        return detail
    return detail[: limit - 3].rstrip() + "..."
