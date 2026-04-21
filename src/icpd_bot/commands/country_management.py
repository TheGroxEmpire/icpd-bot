from collections.abc import Iterable
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from icpd_bot.db.models import (
    CooperatorCountry,
    HostileProxy,
    IcpdCountry,
    IcpdProxy,
    SanctionedCountry,
    WareraCountryCache,
)
from icpd_bot.services.country_registry import (
    CooperatorCountryService,
    CountryInput,
    HostileProxyService,
    IcpdCountryService,
    IcpdProxyService,
    SanctionedCountryService,
)
from icpd_bot.services.guild_config import GuildConfigService
from icpd_bot.services.permissions import require_council_access, require_read_only_access

if TYPE_CHECKING:
    from icpd_bot.bot.app import ICPDBot


async def send_embed_with_visibility_option(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    post_publicly: bool,
    tag: str | None,
) -> None:
    if not post_publicly:
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    channel = interaction.channel
    if channel is None:
        await interaction.response.send_message(
            "I could not find a channel to post that embed publicly.",
            ephemeral=True,
        )
        return

    tag_text = tag.strip() if tag else ""
    await channel.send(content=tag_text or None, embed=embed)
    await interaction.response.send_message("Posted the embed publicly.", ephemeral=True)


def format_country_lines(records: Iterable[SanctionedCountry | IcpdCountry | CooperatorCountry | IcpdProxy]) -> str:
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


def country_link(country_id: str) -> str:
    return f"https://app.warera.io/country/{country_id}"


def build_country_list_embed(
    *,
    title: str,
    records: Iterable[SanctionedCountry | IcpdCountry | CooperatorCountry | IcpdProxy],
) -> discord.Embed:
    embed = discord.Embed(title=title)
    records_list = list(records)
    if not records_list:
        embed.description = "No entries stored."
        return embed

    def chunk_blocks(blocks: list[str], limit: int = 1024) -> list[str]:
        if not blocks:
            return ["No entries stored."]
        chunks: list[str] = []
        current = ""
        for block in blocks:
            candidate = block if not current else f"{current}\n\n{block}"
            if len(candidate) > limit:
                if current:
                    chunks.append(current)
                    current = block
                else:
                    chunks.append(block[:limit])
                    current = block[limit:]
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    blocks: list[str] = []
    for record in records_list:
        flag = country_flag(record.country_code)
        country_label = f"{flag} [{record.country_name_snapshot}]({country_link(record.country_id)})".strip()
        details = [f"`{record.country_code}`"]
        if isinstance(record, SanctionedCountry):
            details.append(f"Sanction: `{record.sanction_level}`")
        if isinstance(record, IcpdProxy):
            details.append(f"Overlord: {record.overlord_country_name_snapshot}")
        blocks.append(f"**{country_label}**\n" + "\n".join(details))

    midpoint = (len(blocks) + 1) // 2
    left_chunks = chunk_blocks(blocks[:midpoint])
    right_chunks = chunk_blocks(blocks[midpoint:]) if midpoint < len(blocks) else []
    max_rows = max(len(left_chunks), len(right_chunks))
    for row in range(max_rows):
        embed.add_field(
            name="\u200b",
            value=left_chunks[row] if row < len(left_chunks) else "\u200b",
            inline=True,
        )
        embed.add_field(
            name="\u200b",
            value=right_chunks[row] if row < len(right_chunks) else "\u200b",
            inline=True,
        )
        if row != max_rows - 1:
            embed.add_field(name="\u200b", value="\u200b", inline=False)
    return embed


def build_read_only_roles_embed(guild: discord.Guild | None, role_ids: list[int]) -> discord.Embed:
    embed = discord.Embed(title="Read-only Access Roles")
    if not role_ids:
        embed.description = "No read-only roles configured."
        return embed

    lines: list[str] = []
    for role_id in role_ids:
        role = guild.get_role(role_id) if guild is not None else None
        if role is not None:
            lines.append(f"{role.mention}\n`{role.id}`")
        else:
            lines.append(f"`{role_id}`")
    embed.description = "\n\n".join(lines)
    return embed


def _chunk_lines(lines: list[str], limit: int = 1024) -> list[str]:
    if not lines:
        return ["No proxies stored."]

    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) > limit:
            if current:
                chunks.append(current)
                current = line
            else:
                chunks.append(line[:limit])
                current = line[limit:]
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def _format_overlord_section_label(names_and_flags: list[tuple[str, str]]) -> str:
    if not names_and_flags:
        return "Unknown overlord"
    labeled_names = [f"{flag} {name}".strip() if flag else name for name, flag in names_and_flags]
    if len(labeled_names) == 1:
        return labeled_names[0]
    if len(labeled_names) == 2:
        return f"{labeled_names[0]} & {labeled_names[1]}"
    return f"{', '.join(labeled_names[:-1])} & {labeled_names[-1]}"


def build_icpd_proxy_list_embed(
    records: Iterable[IcpdProxy],
    *,
    overlord_codes_by_id: dict[str, str],
    active_population_by_country_id: dict[str, int | None],
) -> discord.Embed:
    embed = discord.Embed(title="ICPD Proxies")
    records_list = sorted(
        records,
        key=lambda record: (
            record.overlord_country_name_snapshot.lower(),
            record.country_name_snapshot.lower(),
        ),
    )
    if not records_list:
        embed.description = "No entries stored."
        return embed

    records_by_country_id: dict[str, list[IcpdProxy]] = {}
    for record in records_list:
        records_by_country_id.setdefault(record.country_id, []).append(record)

    proxies_by_overlord_group: dict[tuple[str, ...], list[IcpdProxy]] = {}
    for country_records in records_by_country_id.values():
        ordered_records = sorted(
            country_records,
            key=lambda record: record.overlord_country_name_snapshot.lower(),
        )
        overlord_group = tuple(record.overlord_country_name_snapshot for record in ordered_records)
        proxies_by_overlord_group.setdefault(overlord_group, []).append(ordered_records[0])

    field_count = 0
    for overlord_group, proxies in sorted(
        proxies_by_overlord_group.items(),
        key=lambda item: (len(item[0]), item[0]),
    ):
        lines = []
        for proxy in sorted(proxies, key=lambda record: record.country_name_snapshot.lower()):
            flag = country_flag(proxy.country_code)
            proxy_label = f"{flag} [{proxy.country_name_snapshot}]({country_link(proxy.country_id)})".strip()
            active_population = active_population_by_country_id.get(proxy.country_id)
            population_label = (
                f" active `{active_population}`"
                if active_population is not None
                else ""
            )
            lines.append(f"- {proxy_label}{population_label}")

        chunks = _chunk_lines(lines)
        overlord_label = _format_overlord_section_label(
            [
                (
                    record.overlord_country_name_snapshot,
                    country_flag(overlord_codes_by_id.get(record.overlord_country_id, "")),
                )
                for record in sorted(
                    records_by_country_id[proxies[0].country_id],
                    key=lambda item: item.overlord_country_name_snapshot.lower(),
                )
                if record.overlord_country_name_snapshot in overlord_group
            ]
        )
        for index, chunk in enumerate(chunks):
            field_name = overlord_label if index == 0 else f"{overlord_label} (cont.)"
            embed.add_field(name=field_name, value=chunk, inline=True)
            field_count += 1
            if field_count % 3 == 0:
                embed.add_field(name="\u200b", value="\u200b", inline=False)

    return embed


def build_hostile_proxy_list_embed(
    records: Iterable[HostileProxy],
    *,
    overlord_codes_by_id: dict[str, str],
    active_population_by_country_id: dict[str, int | None],
) -> discord.Embed:
    embed = discord.Embed(title="Hostile Proxies")
    records_list = sorted(
        records,
        key=lambda record: (
            record.overlord_country_name_snapshot.lower(),
            record.country_name_snapshot.lower(),
        ),
    )
    if not records_list:
        embed.description = "No entries stored."
        return embed

    records_by_country_id: dict[str, list[HostileProxy]] = {}
    for record in records_list:
        records_by_country_id.setdefault(record.country_id, []).append(record)

    proxies_by_overlord_group: dict[tuple[str, ...], list[HostileProxy]] = {}
    for country_records in records_by_country_id.values():
        ordered_records = sorted(
            country_records,
            key=lambda record: record.overlord_country_name_snapshot.lower(),
        )
        overlord_group = tuple(record.overlord_country_name_snapshot for record in ordered_records)
        proxies_by_overlord_group.setdefault(overlord_group, []).append(ordered_records[0])

    field_count = 0
    for overlord_group, proxies in sorted(
        proxies_by_overlord_group.items(),
        key=lambda item: (len(item[0]), item[0]),
    ):
        lines = []
        for proxy in sorted(proxies, key=lambda record: record.country_name_snapshot.lower()):
            flag = country_flag(proxy.country_code)
            proxy_label = f"{flag} [{proxy.country_name_snapshot}]({country_link(proxy.country_id)})".strip()
            active_population = active_population_by_country_id.get(proxy.country_id)
            population_label = f" active `{active_population}`" if active_population is not None else ""
            lines.append(f"- {proxy_label}{population_label}")

        chunks = _chunk_lines(lines)
        overlord_label = _format_overlord_section_label(
            [
                (
                    record.overlord_country_name_snapshot,
                    country_flag(overlord_codes_by_id.get(record.overlord_country_id, "")),
                )
                for record in sorted(
                    records_by_country_id[proxies[0].country_id],
                    key=lambda item: item.overlord_country_name_snapshot.lower(),
                )
                if record.overlord_country_name_snapshot in overlord_group
            ]
        )
        for index, chunk in enumerate(chunks):
            field_name = overlord_label if index == 0 else f"{overlord_label} (cont.)"
            embed.add_field(name=field_name, value=chunk, inline=True)
            field_count += 1
            if field_count % 3 == 0:
                embed.add_field(name="\u200b", value="\u200b", inline=False)

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
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
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
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            removed = await SanctionedCountryService(session).remove(country_id)

        message = "Sanction removed." if removed else "No sanctioned country found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_sanctioned_countries", description="List sanctioned countries.")
    @app_commands.describe(
        post_publicly="Post the embed publicly in this channel",
        tag="Optional tag or message to include when posting publicly",
    )
    async def list_sanctioned_countries(
        interaction: discord.Interaction,
        post_publicly: bool = False,
        tag: str | None = None,
    ) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return
        async with bot.session_factory.session() as session:
            records = await SanctionedCountryService(session).list_all()

        await send_embed_with_visibility_option(
            interaction,
            embed=build_country_list_embed(title="Sanctioned Countries", records=records),
            post_publicly=post_publicly,
            tag=tag,
        )

    @app_commands.command(name="add_icpd_country", description="Add or update an ICPD country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def add_icpd_country(
        interaction: discord.Interaction,
        country_id: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
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
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            removed = await IcpdCountryService(session).remove(country_id)

        message = "ICPD country removed." if removed else "No ICPD country found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_icpd_countries", description="List ICPD countries.")
    @app_commands.describe(
        post_publicly="Post the embed publicly in this channel",
        tag="Optional tag or message to include when posting publicly",
    )
    async def list_icpd_countries(
        interaction: discord.Interaction,
        post_publicly: bool = False,
        tag: str | None = None,
    ) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return
        async with bot.session_factory.session() as session:
            records = await IcpdCountryService(session).list_all()

        await send_embed_with_visibility_option(
            interaction,
            embed=build_country_list_embed(title="ICPD Countries", records=records),
            post_publicly=post_publicly,
            tag=tag,
        )

    @app_commands.command(name="add_icpd_proxy", description="Add or update an ICPD proxy country.")
    @app_commands.describe(
        country_id="Pick the proxy country",
        overlord_country_id="Pick one ICPD owner country",
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
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
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
            if await session.get(IcpdCountry, overlord_country_id) is None:
                await interaction.response.send_message(
                    f"`{overlord_country.name}` is not stored as an ICPD country. "
                    "Add it with `/add_icpd_country` first.",
                    ephemeral=True,
                )
                return

            try:
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
            except IntegrityError:
                await interaction.response.send_message(
                    "Could not store that ICPD proxy because the overlord country is not a valid ICPD country.",
                    ephemeral=True,
                )
                return

        await interaction.response.send_message(
            f"Stored ICPD proxy `{country.code.upper()}` under `{overlord_country.code.upper()}`.",
            ephemeral=True,
        )

    @app_commands.command(name="add_hostile_proxy", description="Add or update a hostile proxy country.")
    @app_commands.describe(
        country_id="Pick the proxy country",
        overlord_country_id="Pick one hostile owner country",
    )
    @app_commands.autocomplete(
        country_id=autocomplete_warera_country,
        overlord_country_id=autocomplete_warera_country,
    )
    async def add_hostile_proxy(
        interaction: discord.Interaction,
        country_id: str,
        overlord_country_id: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
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
            await HostileProxyService(session).upsert(
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
            f"Stored hostile proxy `{country.code.upper()}` under `{overlord_country.code.upper()}`.",
            ephemeral=True,
        )

    @app_commands.command(name="add_cooperator_country", description="Add or update a cooperator country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def add_cooperator_country(
        interaction: discord.Interaction,
        country_id: str,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        country = await resolve_warera_country(country_id, bot)
        if country is None:
            await interaction.response.send_message(
                "Country not found in cache. Run `/sync_warera_cache` first.",
                ephemeral=True,
            )
            return

        async with bot.session_factory.session() as session:
            await CooperatorCountryService(session).upsert(
                CountryInput(
                    country_id=country_id,
                    country_code=country.code,
                    country_name=country.name,
                    actor_id=interaction.user.id,
                )
            )

        await interaction.response.send_message(
            f"Stored cooperator country `{country.code.upper()}`.",
            ephemeral=True,
        )

    @app_commands.command(name="remove_cooperator_country", description="Remove a cooperator country.")
    @app_commands.describe(country_id="Pick a Warera country")
    @app_commands.autocomplete(country_id=autocomplete_warera_country)
    async def remove_cooperator_country(interaction: discord.Interaction, country_id: str) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            removed = await CooperatorCountryService(session).remove(country_id)

        message = "Cooperator country removed." if removed else "No cooperator country found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_cooperator_countries", description="List cooperator countries.")
    @app_commands.describe(
        post_publicly="Post the embed publicly in this channel",
        tag="Optional tag or message to include when posting publicly",
    )
    async def list_cooperator_countries(
        interaction: discord.Interaction,
        post_publicly: bool = False,
        tag: str | None = None,
    ) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return

        async with bot.session_factory.session() as session:
            records = await CooperatorCountryService(session).list_all()

        await send_embed_with_visibility_option(
            interaction,
            embed=build_country_list_embed(title="Cooperator Countries", records=records),
            post_publicly=post_publicly,
            tag=tag,
        )

    @app_commands.command(name="remove_icpd_proxy", description="Remove an ICPD proxy country.")
    @app_commands.describe(
        country_id="Pick a proxy country",
        overlord_country_id="Optional ICPD owner country to remove only one proxy link",
    )
    @app_commands.autocomplete(
        country_id=autocomplete_warera_country,
        overlord_country_id=autocomplete_warera_country,
    )
    async def remove_icpd_proxy(
        interaction: discord.Interaction,
        country_id: str,
        overlord_country_id: str | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            removed = await IcpdProxyService(session).remove(country_id, overlord_country_id)

        message = "ICPD proxy removed." if removed else "No ICPD proxy found for that selection."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="remove_hostile_proxy", description="Remove a hostile proxy country.")
    @app_commands.describe(
        country_id="Pick a proxy country",
        overlord_country_id="Optional hostile owner country to remove only one proxy link",
    )
    @app_commands.autocomplete(
        country_id=autocomplete_warera_country,
        overlord_country_id=autocomplete_warera_country,
    )
    async def remove_hostile_proxy(
        interaction: discord.Interaction,
        country_id: str,
        overlord_country_id: str | None = None,
    ) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            removed = await HostileProxyService(session).remove(country_id, overlord_country_id)

        message = "Hostile proxy removed." if removed else "No hostile proxy found for that selection."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_icpd_proxies", description="List ICPD proxy countries.")
    @app_commands.describe(
        post_publicly="Post the embed publicly in this channel",
        tag="Optional tag or message to include when posting publicly",
    )
    async def list_icpd_proxies(
        interaction: discord.Interaction,
        post_publicly: bool = False,
        tag: str | None = None,
    ) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return
        async with bot.session_factory.session() as session:
            records = await IcpdProxyService(session).list_all()
            icpd_countries = await IcpdCountryService(session).list_all()
            proxy_country_ids = sorted({record.country_id for record in records})
            proxy_countries = list(
                await session.scalars(
                    select(WareraCountryCache).where(WareraCountryCache.country_id.in_(proxy_country_ids))
                )
            ) if proxy_country_ids else []
        overlord_codes_by_id = {
            country.country_id: country.country_code
            for country in icpd_countries
        }
        active_population_by_country_id = {
            country.country_id: country.active_population
            for country in proxy_countries
        }

        await send_embed_with_visibility_option(
            interaction,
            embed=build_icpd_proxy_list_embed(
                records,
                overlord_codes_by_id=overlord_codes_by_id,
                active_population_by_country_id=active_population_by_country_id,
            ),
            post_publicly=post_publicly,
            tag=tag,
        )

    @app_commands.command(name="list_hostile_proxies", description="List hostile proxy countries.")
    @app_commands.describe(
        post_publicly="Post the embed publicly in this channel",
        tag="Optional tag or message to include when posting publicly",
    )
    async def list_hostile_proxies(
        interaction: discord.Interaction,
        post_publicly: bool = False,
        tag: str | None = None,
    ) -> None:
        if not await require_read_only_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
            session_factory=bot.session_factory,
        ):
            return

        async with bot.session_factory.session() as session:
            records = await HostileProxyService(session).list_all()
            country_ids = sorted({record.country_id for record in records} | {record.overlord_country_id for record in records})
            cached_countries = list(
                await session.scalars(
                    select(WareraCountryCache).where(WareraCountryCache.country_id.in_(country_ids))
                )
            ) if country_ids else []

        overlord_codes_by_id = {
            country.country_id: country.code
            for country in cached_countries
        }
        active_population_by_country_id = {
            country.country_id: country.active_population
            for country in cached_countries
        }

        await send_embed_with_visibility_option(
            interaction,
            embed=build_hostile_proxy_list_embed(
                records,
                overlord_codes_by_id=overlord_codes_by_id,
                active_population_by_country_id=active_population_by_country_id,
            ),
            post_publicly=post_publicly,
            tag=tag,
        )

    @app_commands.command(name="add_read_only_role", description="Allow a role to use read-only bot commands.")
    async def add_read_only_role(interaction: discord.Interaction, role_id: str) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        try:
            normalized_role_id = int(role_id)
        except ValueError:
            await interaction.response.send_message("Role ID must be numeric.", ephemeral=True)
            return

        guild = interaction.guild
        role = guild.get_role(normalized_role_id) if guild is not None else None
        async with bot.session_factory.session() as session:
            await GuildConfigService(session).add_read_only_role(bot.settings.discord_guild_id, normalized_role_id)

        role_label = role.mention if role is not None else f"`{normalized_role_id}`"
        await interaction.response.send_message(
            f"Granted read-only bot access to {role_label}.",
            ephemeral=True,
        )

    @app_commands.command(name="remove_read_only_role", description="Remove read-only bot access from a role.")
    async def remove_read_only_role(interaction: discord.Interaction, role_id: str) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        try:
            normalized_role_id = int(role_id)
        except ValueError:
            await interaction.response.send_message("Role ID must be numeric.", ephemeral=True)
            return

        async with bot.session_factory.session() as session:
            removed = await GuildConfigService(session).remove_read_only_role(
                bot.settings.discord_guild_id,
                normalized_role_id,
            )

        message = "Read-only role removed." if removed else "No read-only role found for that ID."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="list_read_only_roles", description="List roles that can use read-only bot commands.")
    async def list_read_only_roles(interaction: discord.Interaction) -> None:
        if not await require_council_access(
            interaction,
            home_guild_id=bot.settings.discord_guild_id,
            council_role_id=bot.settings.council_role_id,
        ):
            return

        async with bot.session_factory.session() as session:
            records = await GuildConfigService(session).list_read_only_roles(bot.settings.discord_guild_id)

        await interaction.response.send_message(
            embed=build_read_only_roles_embed(interaction.guild, [record.role_id for record in records]),
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
        add_hostile_proxy,
        add_cooperator_country,
        remove_cooperator_country,
        list_cooperator_countries,
        remove_icpd_proxy,
        remove_hostile_proxy,
        list_icpd_proxies,
        list_hostile_proxies,
        add_read_only_role,
        remove_read_only_role,
        list_read_only_roles,
    ]
