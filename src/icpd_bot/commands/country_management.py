from collections.abc import Iterable
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from sqlalchemy import or_, select

from icpd_bot.db.models import IcpdCountry, IcpdProxy, SanctionedCountry, WareraCountryCache
from icpd_bot.services.country_registry import (
    CountryInput,
    IcpdCountryService,
    IcpdProxyService,
    SanctionedCountryService,
)
from icpd_bot.services.permissions import member_has_role

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


async def require_council(interaction: discord.Interaction, council_role_id: int) -> bool:
    if member_has_role(interaction, council_role_id):
        return True

    message = "This command is restricted to ICPD Council members."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


def format_country_lines(records: Iterable[SanctionedCountry | IcpdCountry | IcpdProxy]) -> str:
    lines: list[str] = []
    for record in records:
        line = f"`{record.country_code}` {record.country_name_snapshot} ({record.country_id})"
        if isinstance(record, SanctionedCountry):
            line = f"{line} [{record.sanction_level}]"
        if isinstance(record, IcpdProxy):
            line = f"{line} -> {record.overlord_country_name_snapshot}"
        lines.append(line)
    return "\n".join(lines) if lines else "No entries stored."


def country_flag(code: str) -> str:
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(127397 + ord(char.upper())) for char in code)


def build_country_list_embed(
    *,
    title: str,
    records: Iterable[SanctionedCountry | IcpdCountry | IcpdProxy],
) -> discord.Embed:
    embed = discord.Embed(title=title)
    records_list = list(records)
    if not records_list:
        embed.description = "No entries stored."
        return embed
    for record in records_list[:25]:
        flag = country_flag(record.country_code)
        line = f"{flag} {record.country_name_snapshot}".strip()
        details = f"`{record.country_code}`\nID: `{record.country_id}`"
        if isinstance(record, SanctionedCountry):
            details = f"{details}\nSanction: `{record.sanction_level}`"
        if isinstance(record, IcpdProxy):
            details = f"{details}\nOverlord: {record.overlord_country_name_snapshot}"
        embed.add_field(name=line, value=details, inline=False)
    return embed


async def autocomplete_sanction_level(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    levels = ["limited", "full"]
    search = current.strip().lower()
    if search:
        levels = [level for level in levels if search in level]
    return [app_commands.Choice(name=level, value=level) for level in levels]


async def autocomplete_warera_country(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    search = current.strip()
    async with interaction.client.session_factory.session() as session:  # type: ignore[attr-defined]
        statement = select(WareraCountryCache).order_by(WareraCountryCache.name).limit(25)
        if search:
            like = f"%{search.lower()}%"
            statement = (
                select(WareraCountryCache)
                .where(
                    or_(
                        WareraCountryCache.name.ilike(like),
                        WareraCountryCache.code.ilike(like),
                    )
                )
                .order_by(WareraCountryCache.name)
                .limit(25)
            )
        records = list(await session.scalars(statement))
    return [
        app_commands.Choice(
            name=f"{record.name} ({record.code.upper()})",
            value=record.country_id,
        )
        for record in records
    ]


async def resolve_warera_country(country_id: str, bot: "ICPDBot") -> WareraCountryCache | None:
    async with bot.session_factory.session() as session:
        return await session.get(WareraCountryCache, country_id)


def build_country_management_commands(bot: "ICPDBot") -> list[app_commands.Command]:
    @app_commands.command(name="add_sanctioned_country", description="Add or update a sanctioned country.")
    @app_commands.describe(
        country_id="Pick a Warera country",
        sanction_level="Sanction level: limited or full",
        sanction_reason="Optional reason for the sanction",
    )
    @app_commands.autocomplete(
        country_id=autocomplete_warera_country,
        sanction_level=autocomplete_sanction_level,
    )
    async def add_sanctioned_country(
        interaction: discord.Interaction,
        country_id: str,
        sanction_level: str,
        sanction_reason: str | None = None,
    ) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        normalized_level = sanction_level.lower().strip()
        if normalized_level not in {"limited", "full"}:
            await interaction.response.send_message(
                "Sanction level must be `limited` or `full`.",
                ephemeral=True,
            )
            return

        country = await resolve_warera_country(country_id, bot)
        if country is None:
            await interaction.response.send_message(
                "Country not found in cache. Run `/sync_warera_cache` first.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            service = SanctionedCountryService(session)
            await service.upsert(
                CountryInput(
                    country_id=country_id,
                    country_code=country.code,
                    country_name=country.name,
                    actor_id=interaction.user.id,
                ),
                sanction_level=normalized_level,
                sanction_reason=sanction_reason,
            )

        await interaction.response.send_message(
            f"Stored sanction for `{country.code.upper()}` as `{normalized_level}`.",
            ephemeral=True,
        )

    @app_commands.command(name="remove_sanctioned_country", description="Remove a sanctioned country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def remove_sanctioned_country(interaction: discord.Interaction, country_id: str) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        async with bot.session_factory.session() as session:
            removed = await SanctionedCountryService(session).remove(country_id)

        message = "Sanction removed." if removed else "No sanctioned country found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_sanctioned_countries", description="List sanctioned countries.")
    async def list_sanctioned_countries(interaction: discord.Interaction) -> None:
        async with bot.session_factory.session() as session:
            records = await SanctionedCountryService(session).list_all()

        await interaction.response.send_message(
            embed=build_country_list_embed(title="Sanctioned Countries", records=records),
            ephemeral=True,
        )

    @app_commands.command(name="add_icpd_country", description="Add or update an ICPD country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def add_icpd_country(
        interaction: discord.Interaction,
        country_id: str,
    ) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        country = await resolve_warera_country(country_id, bot)
        if country is None:
            await interaction.response.send_message(
                "Country not found in cache. Run `/sync_warera_cache` first.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            await IcpdCountryService(session).upsert(
                CountryInput(
                    country_id=country_id,
                    country_code=country.code,
                    country_name=country.name,
                    actor_id=interaction.user.id,
                )
            )

        await interaction.response.send_message(
            f"Stored ICPD country `{country.code.upper()}`.",
            ephemeral=True,
        )

    @app_commands.command(name="remove_icpd_country", description="Remove an ICPD country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def remove_icpd_country(interaction: discord.Interaction, country_id: str) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        async with bot.session_factory.session() as session:
            removed = await IcpdCountryService(session).remove(country_id)

        message = "ICPD country removed." if removed else "No ICPD country found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_icpd_countries", description="List ICPD countries.")
    async def list_icpd_countries(interaction: discord.Interaction) -> None:
        async with bot.session_factory.session() as session:
            records = await IcpdCountryService(session).list_all()

        await interaction.response.send_message(
            embed=build_country_list_embed(title="ICPD Countries", records=records),
            ephemeral=True,
        )

    @app_commands.command(name="add_icpd_proxy", description="Add or update an ICPD proxy country.")
    @app_commands.describe(
        country_id="Pick the proxy country",
        overlord_country_id="Pick the ICPD owner country",
    )
    @app_commands.autocomplete(
        country_id=autocomplete_warera_country,
        overlord_country_id=autocomplete_warera_country,
    )
    async def add_icpd_proxy(
        interaction: discord.Interaction,
        country_id: str,
        overlord_country_id: str,
    ) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        country = await resolve_warera_country(country_id, bot)
        overlord_country = await resolve_warera_country(overlord_country_id, bot)
        if country is None or overlord_country is None:
            await interaction.response.send_message(
                "One or both countries were not found in cache. Run `/sync_warera_cache` first.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            await IcpdProxyService(session).upsert(
                CountryInput(
                    country_id=country_id,
                    country_code=country.code,
                    country_name=country.name,
                    actor_id=interaction.user.id,
                ),
                overlord_country_id=overlord_country_id,
                overlord_country_name=overlord_country.name,
            )

        await interaction.response.send_message(
            f"Stored ICPD proxy `{country.code.upper()}`.",
            ephemeral=True,
        )

    @app_commands.command(name="remove_icpd_proxy", description="Remove an ICPD proxy country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def remove_icpd_proxy(interaction: discord.Interaction, country_id: str) -> None:
        if not await require_council(interaction, bot.settings.council_role_id):
            return

        async with bot.session_factory.session() as session:
            removed = await IcpdProxyService(session).remove(country_id)

        message = "ICPD proxy removed." if removed else "No ICPD proxy found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_icpd_proxies", description="List ICPD proxy countries.")
    async def list_icpd_proxies(interaction: discord.Interaction) -> None:
        async with bot.session_factory.session() as session:
            records = await IcpdProxyService(session).list_all()

        await interaction.response.send_message(
            embed=build_country_list_embed(title="ICPD Proxies", records=records),
            ephemeral=True,
        )

    return [
        add_sanctioned_country,
        remove_sanctioned_country,
        list_sanctioned_countries,
        add_icpd_country,
        remove_icpd_country,
        list_icpd_countries,
        add_icpd_proxy,
        remove_icpd_proxy,
        list_icpd_proxies,
    ]
