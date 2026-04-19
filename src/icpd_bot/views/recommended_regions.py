from __future__ import annotations

from datetime import datetime, timezone

import discord

from icpd_bot.services.recommendations import RecommendationEntry

ITEM_EMOJIS: dict[str, str] = {
    "heavyAmmo": "<:heavyAmmo:1473783426019491892>",
    "lightAmmo": "<:lightAmmo:1473783434336927774>",
    "ammo": "<:ammo:1473783397364011260>",
    "case1": "<:case:1473783402321809644>",
    "case2": "<:eliteCase:1473783406826618961>",
    "bread": "<:bread:1473783399494979776>",
    "grain": "<:grain:1473783422781620386>",
    "fish": "<:fish:1473783419413463050>",
    "cookedFish": "<:cookedFish:1473783417073176719>",
    "steak": "<:steak:1473783451990757386>",
    "livestock": "<:livestock:1473783440884109495>",
    "coca": "<:mysteriousPlant:1473783409045147883>",
    "cocain": "<:pill:1473783411775639782>",
    "iron": "<:iron:1473783428720758859>",
    "lead": "<:lead:1473783432210415626>",
    "oil": "<:oil:1473783443254153430>",
    "limestone": "<:limestone:1473783437642174636>",
    "scraps": "<:scraps:1473783449109266484>",
    "steel": "<:steel:1473783454637232352>",
    "concrete": "<:concrete:1473783414384758875>",
    "petroleum": "<:petroleum:1473783445456027769>",
}

ITEM_DISPLAY_NAMES: dict[str, str] = {
    "heavyAmmo": "Heavy Ammo",
    "lightAmmo": "Light Ammo",
    "ammo": "Ammo",
    "case1": "Case",
    "case2": "Elite Case",
    "bread": "Bread",
    "grain": "Grain",
    "fish": "Fish",
    "cookedFish": "Cooked Fish",
    "steak": "Steak",
    "livestock": "Livestock",
    "coca": "Mysterious Leaf",
    "cocain": "Pill",
    "iron": "Iron",
    "lead": "Lead",
    "oil": "Oil",
    "limestone": "Limestone",
    "scraps": "Scraps",
    "steel": "Steel",
    "concrete": "Concrete",
    "petroleum": "Petroleum",
}


def country_flag(code: str | None) -> str:
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(127397 + ord(char.upper())) for char in code)


def region_link(region_id: str) -> str:
    return f"https://app.warera.io/region/{region_id}"


def country_link(country_id: str | None) -> str | None:
    if not country_id:
        return None
    return f"https://app.warera.io/country/{country_id}"


def item_label(item_name: str) -> str:
    emoji = ITEM_EMOJIS.get(item_name)
    display_name = ITEM_DISPLAY_NAMES.get(item_name, item_name)
    if emoji:
        return f"{emoji} {display_name}"
    return display_name


def status_badge(status: str) -> str:
    return {
        "icpd": "🟩 ICPD",
        "proxy": "🟦 Proxy",
        "cooperator": "🟪 Cooperator",
        "occupied": "🟥 Occupied",
        "manual": "🟨 Council",
    }.get(status, "⬜ Other")


def build_recommended_regions_embed(entries: list[RecommendationEntry]) -> discord.Embed:
    embed = discord.Embed(
        title="Recommended Item Locations",
        description="Current cached recommendations for detected Warera items.",
        timestamp=datetime.now(timezone.utc),
    )
    if not entries:
        embed.add_field(name="No data", value="Run a cache sync first.", inline=False)
        return embed

    # Use two wide text columns so we can show many items without hitting the
    # embed field-count limit that hid entries such as steel.
    formatted_entries: list[str] = []
    for entry in entries:
        flag = country_flag(entry.country_code)
        country_label = f"{flag} {entry.country_name}".strip()
        region_label = f"[{entry.location_name}]({region_link(entry.location_identifier)})"
        country_href = country_link(entry.country_id)
        if country_href:
            country_label = f"[{country_label}]({country_href})"
        extra_lines = [status_badge(entry.ownership_status)]
        if entry.production_bonus_percent is not None:
            extra_lines.append(f"Bonus: {entry.production_bonus_percent:.2f}%")
        else:
            extra_lines.append("\u200b")
        if entry.resistance_display is not None:
            extra_lines.append(f"Resist: {entry.resistance_display}")
        else:
            extra_lines.append("\u200b")
        formatted_entries.append(
            f"**{item_label(entry.good_type)}**\n"
            f"{region_label} (`{entry.location_code}`)\n"
            f"{country_label}\n"
            + "\n".join(extra_lines)
        )

    midpoint = (len(formatted_entries) + 1) // 2
    left_column = "\n\n".join(formatted_entries[:midpoint])
    right_column = "\n\n".join(formatted_entries[midpoint:])

    def chunk_text(text: str, limit: int = 1024) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        current = ""
        for block in text.split("\n\n"):
            addition = block if not current else f"{current}\n\n{block}"
            if len(addition) > limit:
                if current:
                    chunks.append(current)
                    current = block
                else:
                    chunks.append(block[:limit])
                    current = block[limit:]
            else:
                current = addition
        if current:
            chunks.append(current)
        return chunks

    left_chunks = chunk_text(left_column)
    right_chunks = chunk_text(right_column) if right_column else []
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
