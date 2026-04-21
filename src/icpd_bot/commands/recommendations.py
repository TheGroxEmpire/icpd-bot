from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from sqlalchemy import delete, or_, select

from icpd_bot.db.models import (
    GuildConfig,
    IgnoredRecommendationDeposit,
    IgnoredRecommendationRegion,
    LocationRecommendation,
    WareraCountryCache,
    WareraRegionCache,
)
from icpd_bot.services.permissions import require_council_access, require_read_only_access
from icpd_bot.services.recommendations import RecommendationService
from icpd_bot.views.recommended_regions import build_recommended_regions_embed

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


async def autocomplete_goods(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    search = current.strip().lower()
    async with interaction.client.session_factory.session() as session:  # type: ignore[attr-defined]
        countries = list(await session.scalars(select(WareraCountryCache)))
    goods = sorted({country.production_specialization for country in countries if country.production_specialization})
    if search:
        goods = [good for good in goods if search in good.lower()]
    return [app_commands.Choice(name=good, value=good) for good in goods[:25]]


async def autocomplete_regions(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    search = current.strip()
    async with interaction.client.session_factory.session() as session:  # type: ignore[attr-defined]
        statement = select(WareraRegionCache).order_by(WareraRegionCache.name).limit(25)
        if search:
            like = f"%{search.lower()}%"
            statement = (
                select(WareraRegionCache)
                .where(
                    or_(
                        WareraRegionCache.name.ilike(like),
                        WareraRegionCache.code.ilike(like),
                    )
                )
                .order_by(WareraRegionCache.name)
                .limit(25)
            )
        regions = list(await session.scalars(statement))
    return [
        app_commands.Choice(
            name=f"{region.name} ({region.code.upper()})",
            value=region.region_id,
        )
        for region in regions
    ]


def build_recommendation_commands(bot: "ICPDBot") -> list[app_commands.Command]:
    @app_commands.command(
        name="set_location_recommendation",
        description="Store a council recommendation for a specific good and location.",
    )
    @app_commands.autocomplete(
        good_type=autocomplete_goods,
        location_identifier=autocomplete_regions,
    )
    async def set_location_recommendation(
        interaction: discord.Interaction,
        good_type: str,
        location_identifier: str,
        note: str | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            region = await session.get(WareraRegionCache, location_identifier.strip())
            if region is None:
                await interaction.followup.send(
                    "Location not found in cache. Run `/sync_warera_cache` first.",
                    ephemeral=True,
                )
                return
            existing = await session.get(
                LocationRecommendation,
                {
                    "guild_id": bot.settings.discord_guild_id,
                    "location_identifier": location_identifier.strip(),
                    "good_type": good_type.strip(),
                },
            )
            if existing is None:
                session.add(
                    LocationRecommendation(
                        guild_id=bot.settings.discord_guild_id,
                        good_type=good_type.strip(),
                        location_identifier=location_identifier.strip(),
                        location_name_snapshot=region.name,
                        recommendation_note=note.strip() if note else None,
                        updated_by=interaction.user.id,
                    )
                )
            else:
                existing.location_name_snapshot = region.name
                existing.recommendation_note = note.strip() if note else None
                existing.updated_by = interaction.user.id
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Recommendation updated for {good_type.strip()}: {region.name}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Recommendation stored and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="remove_location_recommendation",
        description="Remove council recommendation overrides for a specific good.",
    )
    @app_commands.autocomplete(good_type=autocomplete_goods)
    async def remove_location_recommendation(
        interaction: discord.Interaction,
        good_type: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        normalized_good_type = good_type.strip()
        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            existing = list(
                await session.scalars(
                    select(LocationRecommendation).where(
                        LocationRecommendation.guild_id == bot.settings.discord_guild_id,
                        LocationRecommendation.good_type == normalized_good_type,
                    )
                )
            )
            if not existing:
                await interaction.followup.send(
                    f"No council recommendation override exists for `{normalized_good_type}`.",
                    ephemeral=True,
                )
                return
            await session.execute(
                delete(LocationRecommendation).where(
                    LocationRecommendation.guild_id == bot.settings.discord_guild_id,
                    LocationRecommendation.good_type == normalized_good_type,
                )
            )
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Recommendation override removed for {normalized_good_type}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Recommendation override removed and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="ignore_recommendation_region",
        description="Temporarily ignore a region in automatic recommendations.",
    )
    @app_commands.autocomplete(location_identifier=autocomplete_regions)
    async def ignore_recommendation_region(
        interaction: discord.Interaction,
        location_identifier: str,
        note: str | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            region = await session.get(WareraRegionCache, location_identifier.strip())
            if region is None:
                await interaction.followup.send(
                    "Location not found in cache. Run `/sync_warera_cache` first.",
                    ephemeral=True,
                )
                return
            existing = await session.get(
                IgnoredRecommendationRegion,
                {
                    "guild_id": bot.settings.discord_guild_id,
                    "region_id": location_identifier.strip(),
                },
            )
            if existing is None:
                session.add(
                    IgnoredRecommendationRegion(
                        guild_id=bot.settings.discord_guild_id,
                        region_id=location_identifier.strip(),
                        region_name_snapshot=region.name,
                        note=note.strip() if note else None,
                        created_by=interaction.user.id,
                    )
                )
            else:
                existing.region_name_snapshot = region.name
                existing.note = note.strip() if note else None
                existing.created_by = interaction.user.id
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Recommendation region ignored: {region.name}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Region ignored and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="ignore_region_deposit",
        description="Temporarily ignore a deposit for one good in one region.",
    )
    @app_commands.autocomplete(
        good_type=autocomplete_goods,
        location_identifier=autocomplete_regions,
    )
    async def ignore_region_deposit(
        interaction: discord.Interaction,
        good_type: str,
        location_identifier: str,
        note: str | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        normalized_good_type = good_type.strip()
        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            region = await session.get(WareraRegionCache, location_identifier.strip())
            if region is None:
                await interaction.followup.send(
                    "Location not found in cache. Run `/sync_warera_cache` first.",
                    ephemeral=True,
                )
                return
            deposit_bonus_percent, expires_at = RecommendationService._deposit_details(region, normalized_good_type)
            if deposit_bonus_percent is None or expires_at is None:
                await interaction.followup.send(
                    "That region does not currently have an active deposit for that good with a known end time.",
                    ephemeral=True,
                )
                return
            existing = await session.get(
                IgnoredRecommendationDeposit,
                {
                    "guild_id": bot.settings.discord_guild_id,
                    "region_id": location_identifier.strip(),
                    "good_type": normalized_good_type,
                },
            )
            if existing is None:
                session.add(
                    IgnoredRecommendationDeposit(
                        guild_id=bot.settings.discord_guild_id,
                        region_id=location_identifier.strip(),
                        good_type=normalized_good_type,
                        region_name_snapshot=region.name,
                        note=note.strip() if note else None,
                        expires_at=expires_at,
                        created_by=interaction.user.id,
                    )
                )
            else:
                existing.region_name_snapshot = region.name
                existing.note = note.strip() if note else None
                existing.expires_at = expires_at
                existing.created_by = interaction.user.id
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Deposit ignored for {normalized_good_type} in {region.name} until {expires_at.isoformat()}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Region deposit ignored temporarily and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="unignore_region_deposit",
        description="Allow an ignored deposit back into recommendations.",
    )
    @app_commands.autocomplete(
        good_type=autocomplete_goods,
        location_identifier=autocomplete_regions,
    )
    async def unignore_region_deposit(
        interaction: discord.Interaction,
        good_type: str,
        location_identifier: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        normalized_good_type = good_type.strip()
        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            existing = await session.get(
                IgnoredRecommendationDeposit,
                {
                    "guild_id": bot.settings.discord_guild_id,
                    "region_id": location_identifier.strip(),
                    "good_type": normalized_good_type,
                },
            )
            if existing is None:
                await interaction.followup.send(
                    "That region deposit is not currently ignored.",
                    ephemeral=True,
                )
                return
            region_name = existing.region_name_snapshot
            await session.delete(existing)
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Deposit restored for {normalized_good_type} in {region_name}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Ignored region deposit removed and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="list_ignored_region_deposits",
        description="List temporarily ignored region deposits.",
    )
    async def list_ignored_region_deposits(interaction: discord.Interaction) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            records = list(
                await session.scalars(
                    select(IgnoredRecommendationDeposit)
                    .where(IgnoredRecommendationDeposit.guild_id == bot.settings.discord_guild_id)
                    .order_by(
                        IgnoredRecommendationDeposit.region_name_snapshot,
                        IgnoredRecommendationDeposit.good_type,
                    )
                )
            )

        now = datetime.now(timezone.utc)
        embed = discord.Embed(title="Ignored Region Deposits")
        active_records = [
            record for record in records if record.expires_at is None or record.expires_at > now
        ]
        if not active_records:
            embed.description = "No ignored region deposits configured."
        else:
            lines = []
            for record in active_records:
                expiry = (
                    f" until <t:{int(record.expires_at.timestamp())}:R>"
                    if record.expires_at is not None
                    else ""
                )
                line = f"- {record.region_name_snapshot} / `{record.good_type}`{expiry}"
                if record.note:
                    line = f"{line} - {record.note}"
                lines.append(line)
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unignore_region",
        description="Allow an ignored region back into automatic recommendations.",
    )
    @app_commands.autocomplete(location_identifier=autocomplete_regions)
    async def unignore_region(
        interaction: discord.Interaction,
        location_identifier: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            existing = await session.get(
                IgnoredRecommendationRegion,
                {
                    "guild_id": bot.settings.discord_guild_id,
                    "region_id": location_identifier.strip(),
                },
            )
            if existing is None:
                await interaction.followup.send(
                    "That region is not currently ignored.",
                    ephemeral=True,
                )
                return
            region_name = existing.region_name_snapshot
            await session.delete(existing)
            guild_config = await session.get(GuildConfig, bot.settings.discord_guild_id)

        if guild_config and guild_config.alert_channel_id:
            await bot.alert_service.send_to_channel(
                guild_config.alert_channel_id,
                f"Recommendation region restored: {region_name}.",
                role_id=guild_config.alert_role_id,
            )
        await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send("Ignored region removed and embeds refreshed.", ephemeral=True)

    @app_commands.command(
        name="list_ignored_regions",
        description="List regions currently ignored by automatic recommendations.",
    )
    async def list_ignored_regions(interaction: discord.Interaction) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return

        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            records = list(
                await session.scalars(
                    select(IgnoredRecommendationRegion)
                    .where(IgnoredRecommendationRegion.guild_id == bot.settings.discord_guild_id)
                    .order_by(IgnoredRecommendationRegion.region_name_snapshot)
                )
            )

        embed = discord.Embed(title="Ignored Recommendation Regions")
        if not records:
            embed.description = "No ignored regions configured."
        else:
            lines = []
            for record in records:
                line = f"- {record.region_name_snapshot} (`{record.region_id}`)"
                if record.note:
                    line = f"{line} - {record.note}"
                lines.append(line)
            embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="show_recommended_regions",
        description="Show the current recommended locations embed from cached data.",
    )
    async def show_recommended_regions(interaction: discord.Interaction) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return
        await interaction.response.defer(ephemeral=True)
        async with bot.session_factory.session() as session:
            entries = await RecommendationService(session).build_recommendations(bot.settings.discord_guild_id)
        await interaction.followup.send(embed=build_recommended_regions_embed(entries), ephemeral=True)

    @app_commands.command(
        name="start_list_recommended_region",
        description="Create and track a managed recommended-region embed in this channel.",
    )
    async def start_list_recommended_region(
        interaction: discord.Interaction,
        refresh_interval_minutes: int | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return
        await interaction.response.defer(ephemeral=True)
        interval = refresh_interval_minutes or bot.settings.recommended_region_refresh_minutes
        async with bot.session_factory.session() as session:
            entries = await RecommendationService(session).build_recommendations(bot.settings.discord_guild_id)
        embed = build_recommended_regions_embed(entries)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("This command must be used in a text channel.", ephemeral=True)
            return
        message = await channel.send(embed=embed)
        async with bot.session_factory.session() as session:
            await bot.managed_embed_service_factory(session).create_active_list(
                guild_id=bot.settings.discord_guild_id,
                channel_id=message.channel.id,
                message_id=message.id,
                refresh_interval_minutes=interval,
            )
        await interaction.followup.send(
            f"Managed recommendation embed created as message `{message.id}`.",
            ephemeral=True,
        )

    @app_commands.command(
        name="refresh_list_recommended_region",
        description="Refresh tracked recommended-region embeds now.",
    )
    async def refresh_list_recommended_region(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return
        await interaction.response.defer(ephemeral=True)
        refreshed = await bot.refresh_due_embeds(force_all=True)
        await interaction.followup.send(f"Refreshed {refreshed} managed embed(s).", ephemeral=True)

    @app_commands.command(
        name="stop_list_recommended_region",
        description="Stop refreshing a managed recommended-region embed by message ID.",
    )
    async def stop_list_recommended_region(interaction: discord.Interaction, message_id: str) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return
        try:
            normalized_message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Message ID must be numeric.", ephemeral=True)
            return
        async with bot.session_factory.session() as session:
            deactivated = await bot.managed_embed_service_factory(session).deactivate(normalized_message_id)
        await interaction.response.send_message(
            "Managed embed stopped." if deactivated else "No managed embed found for that message ID.",
            ephemeral=True,
        )

    return [
        set_location_recommendation,
        remove_location_recommendation,
        show_recommended_regions,
        ignore_recommendation_region,
        ignore_region_deposit,
        unignore_region,
        unignore_region_deposit,
        list_ignored_regions,
        list_ignored_region_deposits,
        start_list_recommended_region,
        refresh_list_recommended_region,
        stop_list_recommended_region,
    ]
