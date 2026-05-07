from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import (
    CooperatorProxy,
    HostileProxy,
    IcpdProxy,
    ProxyActivePopulationAlertState,
    SanctionedCountry,
    SpecializationAlertState,
    SyncState,
    WareraCountryCache,
    WareraPartyCache,
    WareraRegionCache,
)
from icpd_bot.integrations.warera import WareraClient


@dataclass(slots=True)
class WareraSyncCounts:
    countries: int
    regions: int
    specialization_changes: list[str] = field(default_factory=list)
    proxy_active_population_warnings: list[str] = field(default_factory=list)


class WareraSyncService:
    PARTY_BATCH_SIZE = 100

    def __init__(self, session: AsyncSession, client: WareraClient) -> None:
        self.session = session
        self.client = client

    async def sync(self) -> WareraSyncCounts:
        sanctioned_ids = {
            country_id
            for country_id in await self.session.scalars(select(SanctionedCountry.country_id))
        }
        countries = await self.client.get_all_countries()
        regions = await self.client.get_regions_object()
        specialization_changes: list[str] = []
        live_country_ids = {self._as_id(payload["_id"]) for payload in countries}
        live_region_ids = {self._as_id(region_id) for region_id in regions}

        await self.session.execute(
            delete(WareraCountryCache).where(WareraCountryCache.country_id.not_in(live_country_ids))
        )
        await self.session.execute(
            delete(WareraRegionCache).where(WareraRegionCache.region_id.not_in(live_region_ids))
        )

        for payload in countries:
            country_id, previous_specialization, record = await self._upsert_country_cache(payload)

            if (
                country_id in sanctioned_ids
                and previous_specialization != record.production_specialization
            ):
                fingerprint = record.production_specialization or "none"
                alert_state = await self.session.get(SpecializationAlertState, country_id)
                if alert_state is None:
                    alert_state = SpecializationAlertState(
                        country_id=country_id,
                        last_known_specialization_fingerprint=fingerprint,
                        last_alerted_fingerprint=None,
                    )
                    self.session.add(alert_state)
                elif alert_state.last_known_specialization_fingerprint != fingerprint:
                    specialization_changes.append(
                        f"{record.name} specialization changed from "
                        f"{previous_specialization or 'none'} to "
                        f"{record.production_specialization or 'none'}."
                    )
                    alert_state.last_known_specialization_fingerprint = fingerprint
                else:
                    alert_state.last_known_specialization_fingerprint = fingerprint

        for region_id, payload in regions.items():
            normalized_region_id = self._as_id(region_id)
            record = await self.session.get(WareraRegionCache, normalized_region_id)
            if record is None:
                record = WareraRegionCache(region_id=normalized_region_id)
                self.session.add(record)

            record.code = str(payload.get("code", "")).lower()
            record.name = str(payload.get("name", ""))
            record.country_id = self._as_id(payload.get("country"))
            record.initial_country_id = self._as_optional_id(payload.get("initialCountry"))
            record.resistance = self._to_optional_int(payload.get("resistance"))
            record.resistance_max = self._to_optional_int(payload.get("resistanceMax"))
            record.development = self._to_optional_float(payload.get("development"))
            record.strategic_resource = self._string_or_none(payload.get("strategicResource"))
            record.raw_payload = json.dumps(payload, separators=(",", ":"), default=str)
            record.fetched_at = datetime.now(UTC)

        now = datetime.now(UTC)
        party_ids = sorted(
            {
                party_id
                for payload in countries
                if (
                    party_id := self._as_optional_embedded_id(payload.get("rulingParty"))
                ) is not None
            }
        )
        existing_party_records = {
            record.party_id: record
            for record in await self.session.scalars(
                select(WareraPartyCache).where(WareraPartyCache.party_id.in_(party_ids))
            )
        } if party_ids else {}

        stale_party_ids = party_ids

        for party_chunk in self._chunked(stale_party_ids, self.PARTY_BATCH_SIZE):
            try:
                payloads = await self.client.get_parties_by_id(party_chunk)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Keep the sync usable with cached party data when the API rate-limits us.
                    break
                raise

            for party_id in party_chunk:
                payload = payloads.get(party_id)
                if payload is None:
                    continue
                record = existing_party_records.get(party_id)
                if record is None:
                    record = WareraPartyCache(party_id=party_id)
                    self.session.add(record)
                    existing_party_records[party_id] = record

                record.name = str(payload.get("name", ""))
                record.country_id = self._as_optional_id(payload.get("country"))
                ethics = payload.get("ethics")
                record.industrialism = self._to_optional_int(
                    ethics.get("industrialism") if isinstance(ethics, dict) else None
                )
                record.raw_payload = json.dumps(payload, separators=(",", ":"), default=str)
                record.fetched_at = now

        proxy_active_population_warnings = await self._build_proxy_active_population_warnings()

        sync_state = await self.session.get(SyncState, "warera_sync")
        if sync_state is None:
            sync_state = SyncState(job_name="warera_sync")
            self.session.add(sync_state)

        counts = WareraSyncCounts(
            countries=len(countries),
            regions=len(regions),
            specialization_changes=specialization_changes,
            proxy_active_population_warnings=proxy_active_population_warnings,
        )
        sync_state.last_success_at = now
        sync_state.last_error = None
        sync_state.row_counts = json.dumps(
            {
                "countries": counts.countries,
                "regions": counts.regions,
                "specialization_changes": len(counts.specialization_changes),
                "proxy_active_population_warnings": len(counts.proxy_active_population_warnings),
            },
            separators=(",", ":"),
        )
        return counts

    async def sync_countries_by_id(self, country_ids: Iterable[str]) -> int:
        normalized_country_ids = sorted(
            {country_id.strip() for country_id in country_ids if country_id.strip()}
        )
        for country_id in normalized_country_ids:
            payload = await self.client.get_country_by_id(country_id)
            await self._upsert_country_cache(payload)
        return len(normalized_country_ids)

    async def _upsert_country_cache(
        self,
        payload: dict[str, object],
    ) -> tuple[str, str | None, WareraCountryCache]:
        country_id = self._as_id(payload["_id"])
        record = await self.session.get(WareraCountryCache, country_id)
        if record is None:
            record = WareraCountryCache(country_id=country_id)
            self.session.add(record)
        previous_specialization = record.production_specialization

        record.code = str(payload.get("code", "")).lower()
        record.name = str(payload.get("name", ""))
        record.production_specialization = self._string_or_none(payload.get("specializedItem"))
        record.active_population = self._extract_active_population(payload)
        record.raw_payload = json.dumps(payload, separators=(",", ":"), default=str)
        record.fetched_at = datetime.now(UTC)
        return country_id, previous_specialization, record

    async def _build_proxy_active_population_warnings(self) -> list[str]:
        proxy_entries = await self._list_unique_proxy_entries()
        if not proxy_entries:
            await self._clear_stale_proxy_active_population_alert_states(set())
            return []

        active_proxy_keys = {(entry.proxy_kind, entry.country_id) for entry in proxy_entries}
        await self._clear_stale_proxy_active_population_alert_states(active_proxy_keys)

        countries_by_id = {
            country.country_id: country
            for country in await self.session.scalars(
                select(WareraCountryCache).where(
                    WareraCountryCache.country_id.in_({entry.country_id for entry in proxy_entries})
                )
            )
        }

        warnings: list[str] = []
        for entry in proxy_entries:
            country = countries_by_id.get(entry.country_id)
            active_population = country.active_population if country is not None else None
            is_below_threshold = active_population is not None and active_population < 4
            state = await self.session.get(
                ProxyActivePopulationAlertState,
                {"proxy_kind": entry.proxy_kind, "country_id": entry.country_id},
            )

            if state is None:
                state = ProxyActivePopulationAlertState(
                    proxy_kind=entry.proxy_kind,
                    country_id=entry.country_id,
                    is_below_threshold=is_below_threshold,
                    last_active_population=active_population,
                )
                self.session.add(state)
                if is_below_threshold:
                    warnings.append(entry.warning(active_population))
                continue

            if is_below_threshold and not state.is_below_threshold:
                warnings.append(entry.warning(active_population))

            state.is_below_threshold = is_below_threshold
            state.last_active_population = active_population

        return warnings

    async def _list_unique_proxy_entries(self) -> list[ProxyActivePopulationEntry]:
        entries_by_key: dict[tuple[str, str], ProxyActivePopulationEntry] = {}
        proxy_models = [
            ("icpd", "ICPD proxy", IcpdProxy),
            ("hostile", "Hostile proxy", HostileProxy),
            ("cooperator", "Cooperator proxy", CooperatorProxy),
        ]
        for proxy_kind, label, model in proxy_models:
            proxies = await self.session.scalars(select(model))
            for proxy in proxies:
                key = (proxy_kind, proxy.country_id)
                entries_by_key.setdefault(
                    key,
                    ProxyActivePopulationEntry(
                        proxy_kind=proxy_kind,
                        label=label,
                        country_id=proxy.country_id,
                        country_code=proxy.country_code,
                        country_name=proxy.country_name_snapshot,
                    ),
                )
        return sorted(entries_by_key.values(), key=lambda entry: (entry.label, entry.country_name))

    async def _clear_stale_proxy_active_population_alert_states(
        self,
        active_proxy_keys: set[tuple[str, str]],
    ) -> None:
        states = await self.session.scalars(select(ProxyActivePopulationAlertState))
        for state in states:
            if (state.proxy_kind, state.country_id) not in active_proxy_keys:
                await self.session.delete(state)

    @staticmethod
    def _as_id(value: object) -> str:
        if value is None:
            raise ValueError("Expected identifier value, got None.")
        text = str(value).strip()
        if not text:
            raise ValueError("Expected identifier value, got empty string.")
        return text

    @staticmethod
    def _as_optional_id(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _as_optional_embedded_id(cls, value: object) -> str | None:
        if isinstance(value, dict):
            return (
                cls._as_optional_id(value.get("_id"))
                or cls._as_optional_id(value.get("id"))
                or cls._as_optional_id(value.get("partyId"))
            )
        return cls._as_optional_id(value)

    @staticmethod
    def _to_optional_int(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, float):
            return int(value)
        if isinstance(value, int):
            return value
        text = str(value)
        if text == "":
            return None
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def _to_optional_float(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, int | float):
            return float(value)
        text = str(value)
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _extract_active_population(cls, payload: dict[str, object]) -> int | None:
        rankings = payload.get("rankings")
        if not isinstance(rankings, dict):
            return None
        active_population = rankings.get("countryActivePopulation")
        if not isinstance(active_population, dict):
            return None
        return cls._to_optional_int(active_population.get("value"))

    @staticmethod
    def _chunked(values: list[str], size: int) -> list[list[str]]:
        if size <= 0:
            return [values]
        return [values[index:index + size] for index in range(0, len(values), size)]


@dataclass(frozen=True, slots=True)
class ProxyActivePopulationEntry:
    proxy_kind: str
    label: str
    country_id: str
    country_code: str
    country_name: str

    def warning(self, active_population: int) -> str:
        flag = self._country_flag(self.country_code)
        country_label = f"{flag} {self.country_name}".strip()
        return (
            f"{self.label}: {country_label} active population is below 4 "
            f"(`{active_population}`)."
        )

    @staticmethod
    def _country_flag(code: str) -> str:
        if len(code) != 2 or not code.isalpha():
            return ""
        return "".join(chr(127397 + ord(char.upper())) for char in code)
