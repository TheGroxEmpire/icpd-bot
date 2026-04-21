import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from icpd_bot.db.base import Base
from icpd_bot.db.models import SyncState, WareraCountryCache
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
