import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from icpd_bot.db.base import Base
from icpd_bot.db.models import (
    CooperatorProxy,
    HostileProxy,
    IcpdProxy,
    SyncState,
    WareraCountryCache,
    WareraPartyCache,
    WareraRegionCache,
)
from icpd_bot.services.warera_sync import WareraSyncService


class FakeWareraClient:
    async def get_all_countries(self) -> list[dict[str, object]]:
        return [
            {
                "_id": "country-1",
                "code": "bn",
                "name": "Brunei",
                "specializedItem": "oil",
                "rankings": {
                    "countryActivePopulation": {
                        "value": 13,
                    }
                },
            }
        ]

    async def get_regions_object(self) -> dict[str, dict[str, object]]:
        return {}

    async def get_country_by_id(self, country_id: str) -> dict[str, object]:
        return {
            "_id": country_id,
            "code": "bn",
            "name": "Brunei",
            "specializedItem": "oil",
            "rankings": {
                "countryActivePopulation": {
                    "value": 27,
                }
            },
        }

    async def get_parties_by_id(self, party_ids: list[str]) -> dict[str, dict[str, object]]:
        return {}


class FakeWareraClientWithEmbeddedParty:
    def __init__(self) -> None:
        self.requested_party_ids: list[str] = []

    async def get_all_countries(self) -> list[dict[str, object]]:
        return [
            {
                "_id": "country-1",
                "code": "ve",
                "name": "Venezuela",
                "specializedItem": "steel",
                "rulingParty": {"_id": "party-1"},
            }
        ]

    async def get_regions_object(self) -> dict[str, dict[str, object]]:
        return {}

    async def get_parties_by_id(self, party_ids: list[str]) -> dict[str, dict[str, object]]:
        self.requested_party_ids.extend(party_ids)
        return {
            "party-1": {
                "name": "Industrialists",
                "country": "country-1",
                "ethics": {"industrialism": 2},
            }
        }


class FakeWareraClientWithProxyPopulation:
    def __init__(self, active_population: int) -> None:
        self.active_population = active_population

    async def get_all_countries(self) -> list[dict[str, object]]:
        return [
            {
                "_id": "proxy-1",
                "code": "bn",
                "name": "Brunei",
                "specializedItem": None,
                "rankings": {
                    "countryActivePopulation": {
                        "value": self.active_population,
                    }
                },
            }
        ]

    async def get_regions_object(self) -> dict[str, dict[str, object]]:
        return {}

    async def get_parties_by_id(self, party_ids: list[str]) -> dict[str, dict[str, object]]:
        return {}


@pytest.mark.asyncio
async def test_sync_stores_country_active_population() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        counts = await WareraSyncService(session, FakeWareraClient()).sync()
        await session.commit()

        country = await session.get(WareraCountryCache, "country-1")
        sync_state = await session.get(SyncState, "warera_sync")

    await engine.dispose()

    assert counts.countries == 1
    assert country is not None
    assert country.active_population == 13
    assert sync_state is not None


@pytest.mark.asyncio
async def test_sync_removes_stale_regions_not_returned_by_upstream() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            WareraRegionCache(
                region_id="stale-region",
                code="stale-region",
                name="Stale Region",
                country_id="country-1",
                initial_country_id="country-1",
                resistance=None,
                resistance_max=None,
                development=0.0,
                strategic_resource=None,
                raw_payload="{}",
            )
        )
        await session.commit()

        counts = await WareraSyncService(session, FakeWareraClient()).sync()
        await session.commit()

        region = await session.get(WareraRegionCache, "stale-region")

    await engine.dispose()

    assert counts.regions == 0
    assert region is None


@pytest.mark.asyncio
async def test_sync_loads_parties_when_country_payload_embeds_ruling_party() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    client = FakeWareraClientWithEmbeddedParty()
    async with session_factory() as session:
        await WareraSyncService(session, client).sync()
        await session.commit()

        party = await session.get(WareraPartyCache, "party-1")

    await engine.dispose()

    assert client.requested_party_ids == ["party-1"]
    assert party is not None
    assert party.industrialism == 2


@pytest.mark.asyncio
async def test_sync_countries_by_id_updates_country_active_population() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            WareraCountryCache(
                country_id="country-1",
                code="bn",
                name="Brunei",
                active_population=13,
                raw_payload="{}",
            )
        )
        await session.commit()

        updated = await WareraSyncService(session, FakeWareraClient()).sync_countries_by_id(
            ["country-1"]
        )
        await session.commit()

        country = await session.get(WareraCountryCache, "country-1")

    await engine.dispose()

    assert updated == 1
    assert country is not None
    assert country.active_population == 27


@pytest.mark.asyncio
async def test_sync_warns_once_when_proxy_active_population_is_below_threshold() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            IcpdProxy(
                country_id="proxy-1",
                country_code="BN",
                country_name_snapshot="Brunei",
                overlord_country_id="icpd-1",
                overlord_country_name_snapshot="ICPD Owner",
                created_by=1,
            )
        )
        await session.commit()

        first_counts = await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=3),
        ).sync()
        await session.commit()

        second_counts = await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=2),
        ).sync()
        await session.commit()

    await engine.dispose()

    assert first_counts.proxy_active_population_warnings == [
        "ICPD proxy: 🇧🇳 Brunei active population is below 4 (`3`)."
    ]
    assert second_counts.proxy_active_population_warnings == []


@pytest.mark.asyncio
async def test_sync_warns_again_after_proxy_active_population_recovers_and_drops() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            HostileProxy(
                country_id="proxy-1",
                country_code="BN",
                country_name_snapshot="Brunei",
                overlord_country_id="hostile-1",
                overlord_country_name_snapshot="Hostile Owner",
                created_by=1,
            )
        )
        await session.commit()

        await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=3),
        ).sync()
        await session.commit()

        recovered_counts = await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=4),
        ).sync()
        await session.commit()

        dropped_counts = await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=1),
        ).sync()
        await session.commit()

    await engine.dispose()

    assert recovered_counts.proxy_active_population_warnings == []
    assert dropped_counts.proxy_active_population_warnings == [
        "Hostile proxy: 🇧🇳 Brunei active population is below 4 (`1`)."
    ]


@pytest.mark.asyncio
async def test_sync_warns_for_cooperator_proxy_active_population() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            CooperatorProxy(
                country_id="proxy-1",
                country_code="BN",
                country_name_snapshot="Brunei",
                overlord_country_id="cooperator-1",
                overlord_country_name_snapshot="Cooperator Owner",
                created_by=1,
            )
        )
        await session.commit()

        counts = await WareraSyncService(
            session,
            FakeWareraClientWithProxyPopulation(active_population=0),
        ).sync()
        await session.commit()

    await engine.dispose()

    assert counts.proxy_active_population_warnings == [
        "Cooperator proxy: 🇧🇳 Brunei active population is below 4 (`0`)."
    ]
