from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, cast

import httpx


WareraCountryPayload = dict[str, Any]
WareraPartyPayload = dict[str, Any]
WareraRegionPayload = dict[str, Any]


class WareraApiError(RuntimeError):
    """Raised when the Warera API returns an unexpected response."""


logger = logging.getLogger(__name__)


class WareraClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-API-Key"] = token

        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers=headers,
            timeout=timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> WareraClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def get_all_countries(self) -> list[WareraCountryPayload]:
        data = await self._get("country.getAllCountries")
        if not isinstance(data, list):
            raise WareraApiError("Expected country.getAllCountries to return a list.")
        return [self._as_dict(item, "country.getAllCountries item") for item in data]

    async def get_country_by_id(self, country_id: str) -> WareraCountryPayload:
        data = await self._get("country.getCountryById", {"countryId": country_id})
        return self._as_dict(data, "country.getCountryById response")

    async def get_regions_object(self) -> dict[str, WareraRegionPayload]:
        data = await self._get("region.getRegionsObject")
        if not isinstance(data, Mapping):
            raise WareraApiError("Expected region.getRegionsObject to return an object.")
        return {
            str(region_id): self._as_dict(payload, f"region payload {region_id}")
            for region_id, payload in data.items()
        }

    async def get_party_by_id(self, party_id: str) -> WareraPartyPayload:
        data = await self._get("party.getById", {"partyId": party_id})
        return self._as_dict(data, "party.getById response")

    async def get_parties_by_id(self, party_ids: list[str]) -> dict[str, WareraPartyPayload]:
        normalized_party_ids = [party_id.strip() for party_id in party_ids if party_id and party_id.strip()]
        if not normalized_party_ids:
            return {}

        endpoint = ",".join("party.getById" for _ in normalized_party_ids)
        batch_payload = {
            str(index): {"partyId": party_id}
            for index, party_id in enumerate(normalized_party_ids)
        }
        data = await self._get_batch(endpoint, batch_payload)
        results: dict[str, WareraPartyPayload] = {}
        for index, item in enumerate(data):
            party_payload = self._as_dict(item, f"party.getById batch response {index}")
            party_id = normalized_party_ids[index]
            results[party_id] = party_payload
        return results

    async def _get(self, endpoint: str, input_payload: Mapping[str, Any] | None = None) -> Any:
        response = await self._client.post(endpoint, json=dict(input_payload or {}))
        response.raise_for_status()
        self._log_rate_limit_headers(endpoint, response)
        payload = response.json()

        if not isinstance(payload, Mapping):
            raise WareraApiError(f"Expected {endpoint} to return a JSON object.")
        result = payload.get("result")
        if not isinstance(result, Mapping) or "data" not in result:
            raise WareraApiError(f"Expected {endpoint} response to contain result.data.")
        return result["data"]

    async def _get_batch(self, endpoint: str, input_payload: Mapping[str, Any]) -> list[Any]:
        response = await self._client.post(endpoint, params={"batch": "1"}, json=dict(input_payload))
        response.raise_for_status()
        self._log_rate_limit_headers(endpoint, response)
        payload = response.json()

        if not isinstance(payload, list):
            raise WareraApiError(f"Expected batched {endpoint} response to return a JSON array.")

        results: list[Any] = []
        for item in payload:
            if not isinstance(item, Mapping):
                raise WareraApiError(f"Expected batched {endpoint} entry to be an object.")
            if "error" in item:
                raise WareraApiError(f"Batched {endpoint} response contained an error entry.")
            result = item.get("result")
            if not isinstance(result, Mapping) or "data" not in result:
                raise WareraApiError(f"Expected batched {endpoint} entry to contain result.data.")
            results.append(result["data"])
        return results

    @staticmethod
    def _as_dict(value: Any, context: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise WareraApiError(f"Expected {context} to be an object.")
        return dict(cast(Mapping[str, Any], value))

    @staticmethod
    def _log_rate_limit_headers(endpoint: str, response: httpx.Response) -> None:
        limit = response.headers.get("ratelimit-limit")
        remaining = response.headers.get("ratelimit-remaining")
        reset = response.headers.get("ratelimit-reset")
        if limit or remaining or reset:
            logger.info(
                "Warera rate limit for %s: limit=%s remaining=%s reset=%s",
                endpoint,
                limit or "?",
                remaining or "?",
                reset or "?",
            )
