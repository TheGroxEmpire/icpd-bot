from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import (
    CooperatorCountry,
    CooperatorProxy,
    IgnoredRecommendationDeposit,
    IgnoredRecommendationRegion,
    IcpdCountry,
    IcpdProxy,
    LocationRecommendation,
    SanctionedCountry,
    WareraCountryCache,
    WareraPartyCache,
    WareraRegionCache,
)


@dataclass(slots=True)
class RecommendationEntry:
    good_type: str
    location_name: str
    location_code: str
    location_identifier: str
    country_id: str | None
    country_name: str
    country_code: str | None
    source_country_id: str | None
    source_country_name: str | None
    source_country_code: str | None
    ownership_statuses: tuple[str, ...]
    production_bonus_percent: float | None
    deposit_bonus_percent: float | None
    deposit_ends_at: datetime | None
    resistance_display: str | None
    development: float | None
    source: str
    note: str


class RecommendationService:
    AMMO_OR_CONSTRUCTION_SPECIALIZATION_IDS = {
        "limestone",
        "iron",
        "concrete",
        "steel",
        "lead",
        "light_ammo",
        "ammo",
        "heavy_ammo",
    }
    FOOD_OR_BUFF_DEPOSIT_IDS = {"grain", "livestock", "fish", "mysterious_plant"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_recommendations(self, guild_id: int) -> list[RecommendationEntry]:
        countries = list(await self.session.scalars(select(WareraCountryCache)))
        parties = list(await self.session.scalars(select(WareraPartyCache)))
        regions = list(await self.session.scalars(select(WareraRegionCache)))
        sanctions = list(await self.session.scalars(select(SanctionedCountry)))
        proxies = list(await self.session.scalars(select(IcpdProxy)))
        cooperators = list(await self.session.scalars(select(CooperatorCountry)))
        cooperator_proxies = list(await self.session.scalars(select(CooperatorProxy)))
        manual = list(
            await self.session.scalars(
                select(LocationRecommendation)
                .where(LocationRecommendation.guild_id == guild_id)
                .order_by(LocationRecommendation.good_type, LocationRecommendation.updated_at.desc())
            )
        )
        ignored_regions = list(
            await self.session.scalars(
                select(IgnoredRecommendationRegion).where(IgnoredRecommendationRegion.guild_id == guild_id)
            )
        )
        ignored_deposits = list(
            await self.session.scalars(
                select(IgnoredRecommendationDeposit).where(IgnoredRecommendationDeposit.guild_id == guild_id)
            )
        )

        countries_by_id = {country.country_id: country for country in countries}
        parties_by_id = {party.party_id: party for party in parties}
        sanctions_by_id = {country.country_id: country for country in sanctions}
        proxy_country_ids = {proxy.country_id for proxy in proxies}
        cooperator_country_ids = {country.country_id for country in cooperators} | {
            proxy.country_id for proxy in cooperator_proxies
        }
        icpd_country_ids = {country.country_id for country in await self.session.scalars(select(IcpdCountry))}
        ignored_region_ids = {record.region_id for record in ignored_regions}
        active_ignored_deposit_keys = {
            (record.region_id, self._resolve_material_id(record.good_type))
            for record in ignored_deposits
            if (
                self._resolve_material_id(record.good_type) is not None
                and (record.expires_at is None or record.expires_at > datetime.now(timezone.utc))
            )
        }
        manual_by_good: dict[str, LocationRecommendation] = {}
        for record in manual:
            manual_by_good.setdefault(record.good_type, record)

        goods = {
            *(country.production_specialization for country in countries if country.production_specialization),
            *manual_by_good.keys(),
        }

        results: list[RecommendationEntry] = []
        for good_type in sorted(goods):
            if good_type in manual_by_good:
                record = manual_by_good[good_type]
                region = next((cached_region for cached_region in regions if cached_region.region_id == record.location_identifier), None)
                country = countries_by_id.get(region.country_id) if region else None
                source_country = (
                    countries_by_id.get(region.initial_country_id)
                    if region and region.initial_country_id and region.initial_country_id != region.country_id
                    else None
                )
                ownership_statuses = (
                    self._ownership_statuses(
                        region=region,
                        icpd_country_ids=icpd_country_ids,
                        proxy_country_ids=proxy_country_ids,
                        cooperator_country_ids=cooperator_country_ids,
                    )
                    if region
                    else ("manual",)
                )
                if "manual" not in ownership_statuses:
                    ownership_statuses = ("manual", *ownership_statuses)
                production_bonus_percent = None
                deposit_bonus_percent = None
                deposit_ends_at = None
                resistance_display = None
                development = None
                if region:
                    deposit_bonus_percent, deposit_ends_at = self._deposit_details(region, good_type)
                    production_bonus_percent = self._total_production_bonus_percent(
                        country=country,
                        region=region,
                        party=parties_by_id.get(self._ruling_party_id(country)),
                        specialization=good_type,
                    )
                    resistance_display = self._resistance_display(region)
                    development = region.development
                results.append(
                    RecommendationEntry(
                        good_type=good_type,
                        location_name=record.location_name_snapshot,
                        location_code=region.code if region else record.location_identifier,
                        location_identifier=record.location_identifier,
                        country_id=region.country_id if region else None,
                        country_name=country.name if country else "Council override",
                        country_code=country.code if country else None,
                        source_country_id=source_country.country_id if source_country else None,
                        source_country_name=source_country.name if source_country else None,
                        source_country_code=source_country.code if source_country else None,
                        ownership_statuses=ownership_statuses,
                        production_bonus_percent=production_bonus_percent,
                        deposit_bonus_percent=deposit_bonus_percent,
                        deposit_ends_at=deposit_ends_at,
                        resistance_display=resistance_display,
                        development=development,
                        source="manual",
                        note=record.recommendation_note or "Council override",
                    )
                )
                continue

            candidate_regions = self._candidate_regions_for_good(
                good_type=good_type,
                regions=regions,
                countries_by_id=countries_by_id,
                sanctions_by_id=sanctions_by_id,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
                ignored_region_ids=ignored_region_ids,
                ignored_region_deposit_keys=active_ignored_deposit_keys,
            )
            eligible_regions = [
                region
                for region in candidate_regions
                if self._is_region_eligible(
                    region=region,
                    countries_by_id=countries_by_id,
                    parties_by_id=parties_by_id,
                    sanctions_by_id=sanctions_by_id,
                    icpd_country_ids=icpd_country_ids,
                    proxy_country_ids=proxy_country_ids,
                )
            ]
            if not eligible_regions:
                continue

            scored_regions = []
            for region in eligible_regions:
                country = countries_by_id.get(region.country_id)
                production_bonus_percent = self._total_production_bonus_percent(
                    country=country,
                    region=region,
                    party=parties_by_id.get(self._ruling_party_id(country)),
                    specialization=good_type,
                    ignored_region_deposit_keys=active_ignored_deposit_keys,
                )
                source_country = countries_by_id.get(region.initial_country_id) if (
                    region.initial_country_id and region.initial_country_id != region.country_id
                ) else None
                if production_bonus_percent <= 0.0:
                    continue
                deposit_bonus_percent, deposit_ends_at = self._deposit_details(
                    region,
                    good_type,
                    ignored_region_deposit_keys=active_ignored_deposit_keys,
                )
                scored_regions.append(
                    (
                        region,
                        country,
                        production_bonus_percent,
                        source_country,
                        deposit_bonus_percent,
                        deposit_ends_at,
                    )
                )
            if not scored_regions:
                continue
            best_region = max(
                scored_regions,
                key=lambda scored: self._recommendation_sort_key(
                    scored[0],
                    scored[2],
                    icpd_country_ids=icpd_country_ids,
                    cooperator_country_ids=cooperator_country_ids,
                    proxy_country_ids=proxy_country_ids,
                ),
            )
            (
                region,
                country,
                production_bonus_percent,
                sanctioned_source_country,
                deposit_bonus_percent,
                deposit_ends_at,
            ) = best_region
            current_sanction = sanctions_by_id.get(region.country_id)
            source_sanction = sanctions_by_id.get(region.initial_country_id) if region.initial_country_id else None
            should_include, note = self._recommendation_visibility(
                good_type=good_type,
                region=region,
                country=country,
                current_sanction=current_sanction,
                source_country=sanctioned_source_country,
                source_sanction=source_sanction,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            if not should_include:
                continue
            ownership_statuses = self._ownership_statuses(
                region=region,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
                cooperator_country_ids=cooperator_country_ids,
            )
            resistance_display = self._resistance_display(region)
            results.append(
                RecommendationEntry(
                    good_type=good_type,
                    location_name=region.name,
                    location_code=region.code,
                    location_identifier=region.region_id,
                    country_id=region.country_id,
                    country_name=country.name if country else region.country_id,
                    country_code=country.code if country else None,
                    source_country_id=sanctioned_source_country.country_id if sanctioned_source_country else None,
                    source_country_name=sanctioned_source_country.name if sanctioned_source_country else None,
                    source_country_code=sanctioned_source_country.code if sanctioned_source_country else None,
                    ownership_statuses=ownership_statuses,
                    production_bonus_percent=production_bonus_percent,
                    deposit_bonus_percent=deposit_bonus_percent,
                    deposit_ends_at=deposit_ends_at,
                    resistance_display=resistance_display,
                    development=region.development,
                    source="automatic",
                    note=note,
                )
            )

        return results

    @classmethod
    def _candidate_regions_for_good(
        cls,
        *,
        good_type: str,
        regions: list[WareraRegionCache],
        countries_by_id: dict[str, WareraCountryCache],
        sanctions_by_id: dict[str, SanctionedCountry],
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
        ignored_region_ids: set[str] | None = None,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> list[WareraRegionCache]:
        normalized_good_type = cls._resolve_material_id(good_type)
        if not normalized_good_type:
            return []
        ignored_region_ids = ignored_region_ids or set()
        ignored_region_deposit_keys = ignored_region_deposit_keys or set()

        limited_sanction_country_ids = {
            country_id
            for country_id, country in countries_by_id.items()
            if cls._resolve_material_id(country.production_specialization) == normalized_good_type
            and sanctions_by_id.get(country_id) is not None
            and sanctions_by_id[country_id].sanction_level == "limited"
        }
        limited_sanction_fallbacks = {
            country_id: cls._limited_sanction_occupied_regions(
                country_id=country_id,
                regions=regions,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            for country_id in limited_sanction_country_ids
        }
        fallback_country_ids = {
            country_id
            for country_id, fallback_regions in limited_sanction_fallbacks.items()
            if fallback_regions
        }
        aligned_specialist_country_ids = {
            country_id
            for country_id, country in countries_by_id.items()
            if cls._resolve_material_id(country.production_specialization) == normalized_good_type
            and cls._is_icpd_aligned_country(
                country_id,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
        }
        aligned_specialist_fallbacks = {
            country_id: cls._aligned_specialist_occupied_regions(
                country_id=country_id,
                regions=regions,
            )
            for country_id in aligned_specialist_country_ids
        }
        fallback_country_ids.update(
            country_id
            for country_id, fallback_regions in aligned_specialist_fallbacks.items()
            if fallback_regions
        )

        candidates_by_id: dict[str, WareraRegionCache] = {
            region.region_id: region
            for region in regions
            if (
                region.region_id not in ignored_region_ids
                and
                countries_by_id.get(region.country_id) is not None
                and (
                    cls._resolve_material_id(countries_by_id[region.country_id].production_specialization)
                    == normalized_good_type
                    or cls._region_matches_good(
                        region,
                        normalized_good_type,
                        ignored_region_deposit_keys=ignored_region_deposit_keys,
                    )
                )
                and region.country_id not in fallback_country_ids
            )
        }

        for fallback_regions in limited_sanction_fallbacks.values():
            for region in fallback_regions:
                if region.region_id not in ignored_region_ids:
                    candidates_by_id.setdefault(region.region_id, region)
        for fallback_regions in aligned_specialist_fallbacks.values():
            for region in fallback_regions:
                if region.region_id not in ignored_region_ids:
                    candidates_by_id.setdefault(region.region_id, region)

        return list(candidates_by_id.values())

    @classmethod
    def _recommendation_sort_key(
        cls,
        region: WareraRegionCache,
        production_bonus_percent: float,
        *,
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> tuple[float, int, float, int, float, str]:
        if region.initial_country_id and region.initial_country_id != region.country_id:
            resistance_ratio, resistance_value, development_value, name = cls._occupied_region_priority_key(region)
            alignment_priority = cls._alignment_priority(
                region.initial_country_id,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            return (
                production_bonus_percent,
                alignment_priority,
                resistance_ratio,
                resistance_value,
                development_value,
                name,
            )
        return (
            production_bonus_percent,
            -1,
            -1.0,
            -1,
            region.development or 0.0,
            region.name,
        )

    @classmethod
    def _recommendation_visibility(
        cls,
        *,
        good_type: str,
        region: WareraRegionCache,
        country: WareraCountryCache | None,
        current_sanction: SanctionedCountry | None,
        source_country: WareraCountryCache | None,
        source_sanction: SanctionedCountry | None,
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> tuple[bool, str]:
        if (
            current_sanction is not None
            and current_sanction.sanction_level == "limited"
            and region.initial_country_id is not None
            and region.initial_country_id != region.country_id
            and country is not None
            and cls._resolve_material_id(country.production_specialization) == cls._resolve_material_id(good_type)
        ):
            source_status = cls._country_alignment_status(
                region.initial_country_id,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            if source_status is not None:
                source_name = source_country.name if source_country else "an ICPD-aligned country"
                return True, (
                    f"{cls._alignment_display_name(source_status)} occupied territory used for "
                    f"limited-sanction {country.name if country else region.country_id} via {source_name}."
                )
            return True, f"Highest-resistance occupied territory in limited-sanction {country.name if country else region.country_id}."
        if (
            source_country is not None
            and cls._resolve_material_id(source_country.production_specialization) == cls._resolve_material_id(good_type)
            and source_sanction is not None
            and source_sanction.sanction_level == "limited"
        ):
            if cls._is_icpd_aligned_country(
                region.country_id,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
            ):
                return True, f"ICPD-aligned occupied territory in limited-sanction {source_country.name}."
            return True, f"Highest-resistance occupied territory in limited-sanction {source_country.name}."
        if (
            source_country is not None
            and region.initial_country_id != region.country_id
            and cls._is_icpd_aligned_country(
                source_country.country_id,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
        ):
            return True, f"Occupied territory of ICPD-aligned country {source_country.name}."
        if country and country.production_specialization == good_type:
            return False, f"Country specialization match in {country.name}."
        return False, "Best eligible cached region."

    @classmethod
    def _region_matches_good(
        cls,
        region: WareraRegionCache,
        good_type: str,
        *,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> bool:
        if cls._is_region_deposit_ignored(
            region.region_id,
            good_type,
            ignored_region_deposit_keys=ignored_region_deposit_keys,
        ):
            return False
        payload = cls._load_payload(region.raw_payload)
        if not payload:
            return False
        deposit = payload.get("deposit")
        if not isinstance(deposit, dict):
            return False
        deposit_item = cls._resolve_material_id(deposit.get("type"))
        return deposit_item == good_type and cls._is_deposit_active(deposit)

    @classmethod
    def _limited_sanction_occupied_regions(
        cls,
        *,
        country_id: str,
        regions: Iterable[WareraRegionCache],
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> list[WareraRegionCache]:
        occupied_regions = [
            region
            for region in regions
            if region.country_id == country_id
            and region.initial_country_id is not None
            and region.initial_country_id != country_id
        ]
        if not occupied_regions:
            return []

        aligned_regions = [
            region
            for region in occupied_regions
            if cls._country_alignment_status(
                region.initial_country_id,
                icpd_country_ids=icpd_country_ids,
                cooperator_country_ids=cooperator_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            is not None
        ]
        if aligned_regions:
            best_alignment_priority = max(
                cls._alignment_priority(
                    region.initial_country_id,
                    icpd_country_ids=icpd_country_ids,
                    cooperator_country_ids=cooperator_country_ids,
                    proxy_country_ids=proxy_country_ids,
                )
                for region in aligned_regions
            )
            return [
                region
                for region in aligned_regions
                if cls._alignment_priority(
                    region.initial_country_id,
                    icpd_country_ids=icpd_country_ids,
                    cooperator_country_ids=cooperator_country_ids,
                    proxy_country_ids=proxy_country_ids,
                )
                == best_alignment_priority
            ]

        return [max(occupied_regions, key=cls._occupied_region_priority_key)]

    @staticmethod
    def _aligned_specialist_occupied_regions(
        *,
        country_id: str,
        regions: Iterable[WareraRegionCache],
    ) -> list[WareraRegionCache]:
        return [
            region
            for region in regions
            if region.initial_country_id == country_id
            and region.country_id != country_id
        ]

    @classmethod
    def _is_region_eligible(
        cls,
        *,
        region: WareraRegionCache,
        countries_by_id: dict[str, WareraCountryCache],
        parties_by_id: dict[str, WareraPartyCache],
        sanctions_by_id: dict[str, SanctionedCountry],
        icpd_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> bool:
        current_sanction = sanctions_by_id.get(region.country_id)
        if current_sanction is not None and current_sanction.sanction_level == "full":
            return False

        initial_country_id = region.initial_country_id
        if not initial_country_id or initial_country_id == region.country_id:
            return True

        initial_sanction = sanctions_by_id.get(initial_country_id)
        if initial_sanction is not None and initial_sanction.sanction_level == "full":
            return False

        return True

    @staticmethod
    def _is_icpd_aligned_country(
        country_id: str | None,
        *,
        icpd_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> bool:
        if not country_id:
            return False
        return country_id in icpd_country_ids or country_id in proxy_country_ids

    @staticmethod
    def _occupied_region_priority_key(region: WareraRegionCache) -> tuple[float, int, float, str]:
        resistance_ratio = 0.0
        if region.resistance is not None and region.resistance_max not in (None, 0):
            resistance_ratio = region.resistance / region.resistance_max
        return (
            resistance_ratio,
            region.resistance or 0,
            region.development or 0.0,
            region.name,
        )

    @staticmethod
    def _ownership_statuses(
        *,
        region: WareraRegionCache,
        icpd_country_ids: set[str],
        proxy_country_ids: set[str],
        cooperator_country_ids: set[str],
    ) -> tuple[str, ...]:
        statuses: list[str] = []

        current_alignment = RecommendationService._country_alignment_status(
            region.country_id,
            icpd_country_ids=icpd_country_ids,
            proxy_country_ids=proxy_country_ids,
            cooperator_country_ids=cooperator_country_ids,
        )
        if current_alignment:
            statuses.append(current_alignment)

        if region.initial_country_id and region.initial_country_id != region.country_id:
            source_alignment = RecommendationService._country_alignment_status(
                region.initial_country_id,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
                cooperator_country_ids=cooperator_country_ids,
            )
            if source_alignment and source_alignment not in statuses:
                statuses.append(source_alignment)
            statuses.append("occupied")

        if statuses:
            return tuple(statuses)
        return ("other",)

    @staticmethod
    def _country_alignment_status(
        country_id: str | None,
        *,
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> str | None:
        if country_id in icpd_country_ids:
            return "icpd"
        if country_id in cooperator_country_ids:
            return "cooperator"
        if country_id in proxy_country_ids:
            return "proxy"
        return None

    @staticmethod
    def _alignment_priority(
        country_id: str | None,
        *,
        icpd_country_ids: set[str],
        cooperator_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> int:
        status = RecommendationService._country_alignment_status(
            country_id,
            icpd_country_ids=icpd_country_ids,
            cooperator_country_ids=cooperator_country_ids,
            proxy_country_ids=proxy_country_ids,
        )
        return {"icpd": 3, "cooperator": 2, "proxy": 1}.get(status, 0)

    @staticmethod
    def _alignment_display_name(status: str) -> str:
        return {
            "icpd": "ICPD",
            "cooperator": "Cooperator",
            "proxy": "Proxy",
        }.get(status, "Aligned")

    @staticmethod
    def _resistance_display(region: WareraRegionCache) -> str | None:
        if region.initial_country_id and region.initial_country_id != region.country_id:
            if region.resistance is not None and region.resistance_max is not None:
                if region.resistance_max <= 0:
                    hijacked_tax_percent = 0.0
                else:
                    hijacked_tax_percent = (region.resistance / region.resistance_max) * 40
                return (
                    f"{region.resistance} / {region.resistance_max} "
                    f"({hijacked_tax_percent:.1f}% hijacked tax)"
                )
        return None

    @staticmethod
    def _normalize_bonus_percent(value: object) -> float:
        try:
            parsed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return round(max(0.0, parsed), 6)

    @staticmethod
    def _resolve_material_id(item_code: str | None) -> str | None:
        if not item_code:
            return None
        raw = str(item_code).strip()
        if not raw:
            return None
        alias_map = {
            "cookedfish": "cooked_fish",
            "coca": "mysterious_plant",
            "cocain": "pill",
            "heavyammo": "heavy_ammo",
            "lightammo": "light_ammo",
            "mysteriousplant": "mysterious_plant",
        }
        normalized_snake_case = ""
        for index, char in enumerate(raw):
            if char.isupper() and index > 0 and raw[index - 1].isalnum():
                normalized_snake_case += "_"
            normalized_snake_case += char
        normalized_snake_case = normalized_snake_case.replace(" ", "_").replace("-", "_").lower()
        aliased = alias_map.get(normalized_snake_case, alias_map.get(raw.lower(), normalized_snake_case))
        return aliased or None

    @staticmethod
    def _party_industrialism(party: WareraPartyCache | None) -> int:
        if party is None or party.industrialism is None:
            return 0
        return max(-2, min(2, int(party.industrialism)))

    @classmethod
    def _party_has_eco_ethics(cls, party: WareraPartyCache | None) -> bool:
        return cls._party_industrialism(party) != 0

    @classmethod
    def _country_has_best_civilization(cls, country: WareraCountryCache | None) -> bool:
        payload = cls._load_payload(country.raw_payload if country else None)
        if not payload:
            return False
        strategic_resources = payload.get("strategicResources")
        rankings = payload.get("rankings")
        strategic_bonus = (
            strategic_resources.get("bonuses", {}).get("productionPercent")
            if isinstance(strategic_resources, dict)
            else None
        )
        ranking_bonus = (
            rankings.get("countryProductionBonus", {}).get("value")
            if isinstance(rankings, dict)
            else None
        )
        return cls._normalize_bonus_percent(
            strategic_bonus if strategic_bonus is not None else ranking_bonus
        ) > 0.0

    @classmethod
    def _party_specialization_bonus_pct(cls, party: WareraPartyCache | None, specialization: str) -> float:
        industrialism = cls._party_industrialism(party)
        if industrialism >= 2:
            return 30.0
        if industrialism >= 1 and specialization in cls.AMMO_OR_CONSTRUCTION_SPECIALIZATION_IDS:
            return 10.0
        return 0.0

    @classmethod
    def _should_apply_country_specialization_bonus(cls, party: WareraPartyCache | None) -> bool:
        return cls._party_industrialism(party) > -2

    @classmethod
    def _should_apply_region_deposit_bonus(cls, party: WareraPartyCache | None, deposit_material_id: str) -> bool:
        industrialism = cls._party_industrialism(party)
        if industrialism >= 2:
            return False
        if industrialism <= -1:
            return deposit_material_id in cls.FOOD_OR_BUFF_DEPOSIT_IDS
        return True

    @classmethod
    def _party_deposit_bonus_pct(cls, party: WareraPartyCache | None, deposit_material_id: str) -> float:
        industrialism = cls._party_industrialism(party)
        if industrialism <= -2 and deposit_material_id in cls.FOOD_OR_BUFF_DEPOSIT_IDS:
            return 30.0
        if industrialism <= -1 and deposit_material_id in cls.FOOD_OR_BUFF_DEPOSIT_IDS:
            return 10.0
        return 0.0

    @classmethod
    def _ruling_party_id(cls, country: WareraCountryCache | None) -> str | None:
        payload = cls._load_payload(country.raw_payload if country else None)
        ruling_party = payload.get("rulingParty")
        return str(ruling_party).strip() if ruling_party else None

    @classmethod
    def _country_specialization_bonus_pct(
        cls,
        country: WareraCountryCache | None,
        specialization: str,
        party: WareraPartyCache | None,
    ) -> float:
        payload = cls._load_payload(country.raw_payload if country else None)
        if not payload:
            return 0.0
        specialized_item = cls._resolve_material_id(payload.get("specializedItem"))
        if specialized_item != specialization:
            return 0.0
        if not cls._should_apply_country_specialization_bonus(party):
            return 0.0
        strategic_resources = payload.get("strategicResources")
        rankings = payload.get("rankings")
        strategic_bonus = (
            strategic_resources.get("bonuses", {}).get("productionPercent")
            if isinstance(strategic_resources, dict)
            else None
        )
        ranking_bonus = (
            rankings.get("countryProductionBonus", {}).get("value")
            if isinstance(rankings, dict)
            else None
        )
        base = cls._normalize_bonus_percent(strategic_bonus if strategic_bonus is not None else ranking_bonus)
        return round(base + cls._party_specialization_bonus_pct(party, specialization), 6)

    @classmethod
    def _region_deposit_bonus_pct(
        cls,
        region: WareraRegionCache,
        specialization: str,
        party: WareraPartyCache | None,
        *,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> float:
        if cls._is_region_deposit_ignored(
            region.region_id,
            specialization,
            ignored_region_deposit_keys=ignored_region_deposit_keys,
        ):
            return 0.0
        payload = cls._load_payload(region.raw_payload)
        if not payload:
            return 0.0
        deposit = payload.get("deposit")
        if not isinstance(deposit, dict):
            return 0.0
        deposit_item = cls._resolve_material_id(deposit.get("type"))
        if deposit_item != specialization:
            return 0.0
        if not cls._should_apply_region_deposit_bonus(party, deposit_item):
            return 0.0
        if not cls._is_deposit_active(deposit):
            return 0.0
        base = cls._normalize_bonus_percent(deposit.get("bonusPercent"))
        return round(base + cls._party_deposit_bonus_pct(party, deposit_item), 6)

    @classmethod
    def _deposit_details(
        cls,
        region: WareraRegionCache,
        specialization: str,
        *,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> tuple[float | None, datetime | None]:
        if cls._is_region_deposit_ignored(
            region.region_id,
            specialization,
            ignored_region_deposit_keys=ignored_region_deposit_keys,
        ):
            return None, None
        payload = cls._load_payload(region.raw_payload)
        deposit = payload.get("deposit")
        if not isinstance(deposit, dict):
            return None, None
        deposit_item = cls._resolve_material_id(deposit.get("type"))
        if deposit_item != cls._resolve_material_id(specialization):
            return None, None
        if not cls._is_deposit_active(deposit):
            return None, None
        return cls._normalize_bonus_percent(deposit.get("bonusPercent")), cls._parse_datetime(deposit.get("endsAt"))

    @classmethod
    def _total_production_bonus_percent(
        cls,
        *,
        country: WareraCountryCache | None,
        region: WareraRegionCache,
        party: WareraPartyCache | None,
        specialization: str,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> float:
        normalized_specialization = cls._resolve_material_id(specialization)
        if not normalized_specialization:
            return 0.0
        return round(
            cls._country_specialization_bonus_pct(country, normalized_specialization, party)
            + cls._region_deposit_bonus_pct(
                region,
                normalized_specialization,
                party,
                ignored_region_deposit_keys=ignored_region_deposit_keys,
            ),
            6,
        )

    @classmethod
    def _is_region_deposit_ignored(
        cls,
        region_id: str,
        specialization: str | None,
        *,
        ignored_region_deposit_keys: set[tuple[str, str | None]] | None = None,
    ) -> bool:
        if ignored_region_deposit_keys is None:
            return False
        return (region_id, cls._resolve_material_id(specialization)) in ignored_region_deposit_keys

    @staticmethod
    def _load_payload(raw_payload: str | None) -> dict[str, object]:
        if not raw_payload:
            return {}
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _is_deposit_active(cls, deposit: dict[str, object]) -> bool:
        now = datetime.now(timezone.utc)
        starts_at = cls._parse_datetime(deposit.get("startsAt"))
        ends_at = cls._parse_datetime(deposit.get("endsAt"))
        if starts_at and now < starts_at:
            return False
        if ends_at and now > ends_at:
            return False
        return True

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
