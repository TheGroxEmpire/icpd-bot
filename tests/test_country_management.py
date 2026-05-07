import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from icpd_bot.commands.country_management import (
    build_cooperator_proxy_list_embed,
    build_country_list_embed,
    build_hostile_proxy_list_embed,
    build_icpd_proxy_list_embed,
    ruling_party_ethics_by_country_id,
)
from icpd_bot.db.base import Base
from icpd_bot.db.models import (
    CooperatorProxy,
    HostileProxy,
    IcpdCountry,
    IcpdProxy,
    WareraCountryCache,
    WareraPartyCache,
)


def test_build_country_list_embed_shows_ruling_party_ethics() -> None:
    embed = build_country_list_embed(
        title="ICPD Countries",
        records=[
            IcpdCountry(
                country_id="country-1",
                country_code="bn",
                country_name_snapshot="Brunei",
                created_by=1,
            )
        ],
        ruling_party_ethics_by_country_id={
            "country-1": "Agrarian Party: Fanatic Agrarist",
        },
    )

    assert len(embed.fields) == 2
    assert "Ruling party ethics: Agrarian Party: Fanatic Agrarist" in embed.fields[0].value


@pytest.mark.asyncio
async def test_ruling_party_ethics_by_country_id_reads_cached_party_payload() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                WareraCountryCache(
                    country_id="country-1",
                    code="bn",
                    name="Brunei",
                    raw_payload='{"rulingParty":{"_id":"party-1"}}',
                ),
                WareraPartyCache(
                    party_id="party-1",
                    name="Agrarian Party",
                    country_id="country-1",
                    industrialism=-2,
                    raw_payload='{"ethics":{"industrialism":-2,"militarism":1}}',
                ),
            ]
        )
        await session.commit()

        labels = await ruling_party_ethics_by_country_id(session, ["country-1"])

    await engine.dispose()

    assert labels == {"country-1": "Agrarian Party: Fanatic Agrarist, Militarist"}


def test_build_icpd_proxy_list_embed_shows_active_population() -> None:
    embed = build_icpd_proxy_list_embed(
        [
            IcpdProxy(
                country_id="proxy-1",
                country_code="bn",
                country_name_snapshot="Brunei",
                overlord_country_id="icpd-1",
                overlord_country_name_snapshot="ICPD",
                created_by=1,
            )
        ],
        overlord_codes_by_id={"icpd-1": "id"},
        active_population_by_country_id={"proxy-1": 13},
        ruling_party_ethics_by_country_id={
            "proxy-1": "Industrialists: Fanatic Industrialist",
        },
    )

    assert len(embed.fields) == 1
    assert "active `13`" in embed.fields[0].value
    assert "ethics Industrialists: Fanatic Industrialist" in embed.fields[0].value


def test_build_hostile_proxy_list_embed_shows_active_population() -> None:
    embed = build_hostile_proxy_list_embed(
        [
            HostileProxy(
                country_id="hostile-1",
                country_code="ru",
                country_name_snapshot="Russia",
                overlord_country_id="hostile-overlord-1",
                overlord_country_name_snapshot="Hostile Overlord",
                created_by=1,
            )
        ],
        overlord_codes_by_id={"hostile-overlord-1": "ir"},
        active_population_by_country_id={"hostile-1": 42},
    )

    assert len(embed.fields) == 1
    assert "active `42`" in embed.fields[0].value


def test_build_cooperator_proxy_list_embed_shows_active_population() -> None:
    embed = build_cooperator_proxy_list_embed(
        [
            CooperatorProxy(
                country_id="coop-1",
                country_code="pl",
                country_name_snapshot="Poland Proxy",
                overlord_country_id="coop-owner-1",
                overlord_country_name_snapshot="Poland",
                created_by=1,
            )
        ],
        overlord_codes_by_id={"coop-owner-1": "pl"},
        active_population_by_country_id={"coop-1": 21},
    )

    assert len(embed.fields) == 1
    assert "active `21`" in embed.fields[0].value
