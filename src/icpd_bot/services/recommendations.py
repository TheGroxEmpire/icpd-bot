from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import (
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
    ownership_status: str
    production_bonus_percent: float | None
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
        manual = list(
            await self.session.scalars(
                select(LocationRecommendation)
                .where(LocationRecommendation.guild_id == guild_id)
                .order_by(LocationRecommendation.good_type, LocationRecommendation.updated_at.desc())
            )
        )

        countries_by_id = {country.country_id: country for country in countries}
        parties_by_id = {party.party_id: party for party in parties}
        sanctions_by_id = {country.country_id: country for country in sanctions}
        proxy_country_ids = {proxy.country_id for proxy in proxies}
        icpd_country_ids = {country.country_id for country in await self.session.scalars(select(IcpdCountry))}
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
                results.append(
                    RecommendationEntry(
                        good_type=good_type,
                        location_name=record.location_name_snapshot,
                        location_code=record.location_identifier,
                        location_identifier=record.location_identifier,
                        country_id=None,
                        country_name="Council override",
                        country_code=None,
                        ownership_status="manual",
                        production_bonus_percent=None,
                        resistance_display=None,
                        development=None,
                        source="manual",
                        note=record.recommendation_note or "Council override",
                    )
                )
                continue

            candidate_regions = [
                region
                for region in regions
                if countries_by_id.get(region.country_id) is not None
                    and countries_by_id[region.country_id].production_specialization == good_type
                
            ]
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

            scored_regions = [
                (
                    region,
                    countries_by_id.get(region.country_id),
                    self._total_production_bonus_percent(
                        country=countries_by_id.get(region.country_id),
                        region=region,
                        party=parties_by_id.get(self._ruling_party_id(countries_by_id.get(region.country_id))),
                        specialization=good_type,
                    ),
                )
                for region in eligible_regions
            ]
            best_region = max(
                scored_regions,
                key=lambda scored: (
                    scored[2],
                    scored[0].development or 0.0,
                    scored[0].name,
                ),
            )
            region, country, production_bonus_percent = best_region
            ownership_status = self._ownership_status(
                region=region,
                icpd_country_ids=icpd_country_ids,
                proxy_country_ids=proxy_country_ids,
            )
            resistance_display = self._resistance_display(region)
            if country and country.production_specialization == good_type:
                note = f"Country specialization match in {country.name}."
            else:
                note = "Best eligible cached region."
            results.append(
                RecommendationEntry(
                    good_type=good_type,
                    location_name=region.name,
                    location_code=region.code,
                    location_identifier=region.region_id,
                    country_id=region.country_id,
                    country_name=country.name if country else region.country_id,
                    country_code=country.code if country else None,
                    ownership_status=ownership_status,
                    production_bonus_percent=production_bonus_percent,
                    resistance_display=resistance_display,
                    development=region.development,
                    source="automatic",
                    note=note,
                )
            )

        return results

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

        initial_is_icpd_aligned = cls._is_icpd_aligned_country(
            initial_country_id,
            icpd_country_ids=icpd_country_ids,
            proxy_country_ids=proxy_country_ids,
        )
        current_is_icpd_aligned = cls._is_icpd_aligned_country(
            region.country_id,
            icpd_country_ids=icpd_country_ids,
            proxy_country_ids=proxy_country_ids,
        )
        if (
            initial_is_icpd_aligned
            and not current_is_icpd_aligned
            and current_sanction is not None
            and current_sanction.sanction_level == "limited"
        ):
            occupier_country = countries_by_id.get(region.country_id)
            occupier_party = parties_by_id.get(cls._ruling_party_id(occupier_country))
            if cls._country_has_best_civilization(occupier_country) and cls._party_has_eco_ethics(occupier_party):
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
    def _ownership_status(
        *,
        region: WareraRegionCache,
        icpd_country_ids: set[str],
        proxy_country_ids: set[str],
    ) -> str:
        if region.country_id in icpd_country_ids:
            return "icpd"
        if region.country_id in proxy_country_ids:
            return "proxy"
        if region.initial_country_id and region.initial_country_id != region.country_id:
            if region.initial_country_id in proxy_country_ids:
                return "cooperator"
            return "occupied"
        return "other"

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
    ) -> float:
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
    def _total_production_bonus_percent(
        cls,
        *,
        country: WareraCountryCache | None,
        region: WareraRegionCache,
        party: WareraPartyCache | None,
        specialization: str,
    ) -> float:
        normalized_specialization = cls._resolve_material_id(specialization)
        if not normalized_specialization:
            return 0.0
        return round(
            cls._country_specialization_bonus_pct(country, normalized_specialization, party)
            + cls._region_deposit_bonus_pct(region, normalized_specialization, party),
            6,
        )

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
