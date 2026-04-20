from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from icpd_bot.db.models import (
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

        for payload in countries:
            country_id = self._as_id(payload["_id"])
            record = await self.session.get(WareraCountryCache, country_id)
            if record is None:
                record = WareraCountryCache(country_id=country_id)
                self.session.add(record)
            previous_specialization = record.production_specialization

            record.code = str(payload.get("code", "")).lower()
            record.name = str(payload.get("name", ""))
            record.production_specialization = self._string_or_none(payload.get("specializedItem"))
            record.raw_payload = json.dumps(payload, separators=(",", ":"), default=str)
            record.fetched_at = datetime.now(timezone.utc)

            if country_id in sanctioned_ids and previous_specialization != record.production_specialization:
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
                        f"{previous_specialization or 'none'} to {record.production_specialization or 'none'}."
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
            record.fetched_at = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        party_ids = sorted(
            {
                str(payload.get("rulingParty")).strip()
                for payload in countries
                if payload.get("rulingParty")
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
                record.industrialism = self._to_optional_int(
                    payload.get("ethics", {}).get("industrialism") if isinstance(payload.get("ethics"), dict) else None
                )
                record.raw_payload = json.dumps(payload, separators=(",", ":"), default=str)
                record.fetched_at = now

        sync_state = await self.session.get(SyncState, "warera_sync")
        if sync_state is None:
            sync_state = SyncState(job_name="warera_sync")
            self.session.add(sync_state)

        counts = WareraSyncCounts(
            countries=len(countries),
            regions=len(regions),
            specialization_changes=specialization_changes,
        )
        sync_state.last_success_at = now
        sync_state.last_error = None
        sync_state.row_counts = json.dumps(
            {
                "countries": counts.countries,
                "regions": counts.regions,
                "specialization_changes": len(counts.specialization_changes),
            },
            separators=(",", ":"),
        )
        return counts

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
        if isinstance(value, (int, float)):
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

    @staticmethod
    def _chunked(values: list[str], size: int) -> list[list[str]]:
        if size <= 0:
            return [values]
        return [values[index:index + size] for index in range(0, len(values), size)]
