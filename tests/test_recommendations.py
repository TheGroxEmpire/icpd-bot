from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from icpd_bot.db.base import Base
from icpd_bot.db.models import (
    IgnoredRecommendationDeposit,
    IgnoredRecommendationRegion,
    CooperatorProxy,
    IcpdProxy,
    LocationRecommendation,
    SanctionedCountry,
    WareraCountryCache,
    WareraPartyCache,
    WareraRegionCache,
)
from icpd_bot.services.recommendations import RecommendationEntry, RecommendationService
from icpd_bot.views.recommended_regions import build_recommended_regions_embed, country_flag, discord_timestamp


def build_region(
    region_id: str,
    *,
    country_id: str,
    initial_country_id: str | None,
    resistance: int | None,
    resistance_max: int | None,
    development: float = 0.0,
) -> WareraRegionCache:
    return WareraRegionCache(
        region_id=region_id,
        code=region_id.lower(),
        name=region_id,
        country_id=country_id,
        initial_country_id=initial_country_id,
        resistance=resistance,
        resistance_max=resistance_max,
        development=development,
        strategic_resource=None,
        raw_payload=None,
    )


def test_limited_sanction_fallback_prefers_proxy_origin_regions() -> None:
    proxy_origin_region = build_region(
        "A1",
        country_id="sanctioned-1",
        initial_country_id="proxy-1",
        resistance=10,
        resistance_max=100,
    )
    occupied_by_other = build_region(
        "A2",
        country_id="sanctioned-1",
        initial_country_id="other-1",
        resistance=80,
        resistance_max=100,
    )

    regions = RecommendationService._limited_sanction_occupied_regions(
        country_id="sanctioned-1",
        regions=[proxy_origin_region, occupied_by_other],
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    )

    assert [region.region_id for region in regions] == ["A1"]


def test_country_flag_maps_uk_to_gb_emoji() -> None:
    assert country_flag("uk") == "🇬🇧"


def test_recommended_regions_embed_links_regions_by_id() -> None:
    embed = build_recommended_regions_embed(
        [
            RecommendationEntry(
                good_type="limestone",
                location_name="South Georgia",
                location_code="uk-south-georgia",
                location_identifier="696a81f5882256e1db118228",
                country_id="country-1",
                country_name="South Africa",
                country_code="za",
                source_country_id="country-2",
                source_country_name="United Kingdom",
                source_country_code="uk",
                ownership_statuses=("cooperator", "occupied"),
                production_bonus_percent=63.0,
                deposit_bonus_percent=None,
                deposit_ends_at=None,
                resistance_display=None,
                development=None,
                source="automatic",
                note="Occupied territory of ICPD-aligned country United Kingdom.",
            )
        ]
    )

    assert "https://app.warera.io/region/696a81f5882256e1db118228" in embed.fields[0].value
    assert "🇬🇧 United Kingdom" in embed.fields[0].value


def test_deposit_details_returns_expiry_for_active_matching_deposit() -> None:
    region = WareraRegionCache(
        region_id="deposit-1",
        code="dep-1",
        name="Deposit",
        country_id="neutral-1",
        initial_country_id="neutral-1",
        resistance=None,
        resistance_max=None,
        development=1.0,
        strategic_resource=None,
        raw_payload=(
            '{"deposit":{"type":"oil","bonusPercent":30,'
            f'"endsAt":"{(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()}"}}'
        ),
    )

    deposit_bonus_percent, expires_at = RecommendationService._deposit_details(region, "oil")

    assert deposit_bonus_percent == 30.0
    assert expires_at is not None


def test_limited_sanction_fallback_uses_highest_resistance_when_no_icpd_alignment() -> None:
    low_resistance = build_region(
        "B1",
        country_id="sanctioned-1",
        initial_country_id="other-1",
        resistance=10,
        resistance_max=100,
        development=5.0,
    )
    high_resistance = build_region(
        "B2",
        country_id="sanctioned-1",
        initial_country_id="other-2",
        resistance=60,
        resistance_max=100,
        development=1.0,
    )
    best_ratio = build_region(
        "B3",
        country_id="sanctioned-1",
        initial_country_id="other-3",
        resistance=50,
        resistance_max=60,
        development=0.0,
    )

    regions = RecommendationService._limited_sanction_occupied_regions(
        country_id="sanctioned-1",
        regions=[low_resistance, high_resistance, best_ratio],
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids=set(),
    )

    assert [region.region_id for region in regions] == ["B3"]


def test_candidate_regions_replace_limited_sanction_home_regions_with_fallback() -> None:
    home_region = build_region(
        "C1",
        country_id="sanctioned-1",
        initial_country_id="sanctioned-1",
        resistance=None,
        resistance_max=None,
    )
    occupied_region = build_region(
        "C2",
        country_id="sanctioned-1",
        initial_country_id="other-1",
        resistance=70,
        resistance_max=100,
    )

    candidates = RecommendationService._candidate_regions_for_good(
        good_type="steel",
        regions=[home_region, occupied_region],
        countries_by_id={
            "sanctioned-1": WareraCountryCache(
                country_id="sanctioned-1",
                code="san",
                name="Sanctioned",
                production_specialization="steel",
                raw_payload=None,
            ),
            "other-1": WareraCountryCache(
                country_id="other-1",
                code="oth",
                name="Other",
                production_specialization=None,
                raw_payload=None,
            ),
        },
        sanctions_by_id={
            "sanctioned-1": SanctionedCountry(
                country_id="sanctioned-1",
                country_code="san",
                country_name_snapshot="Sanctioned",
                sanction_level="limited",
                sanction_reason=None,
                created_by=1,
            )
        },
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids=set(),
        ignored_region_ids=set(),
        ignored_region_deposit_keys=set(),
    )

    assert [region.region_id for region in candidates] == ["C2"]


def test_candidate_regions_replace_icpd_proxy_home_regions_with_occupied_fallback() -> None:
    home_region = build_region(
        "P1",
        country_id="proxy-1",
        initial_country_id="proxy-1",
        resistance=None,
        resistance_max=None,
    )
    occupied_region = build_region(
        "P2",
        country_id="other-1",
        initial_country_id="proxy-1",
        resistance=70,
        resistance_max=100,
    )

    candidates = RecommendationService._candidate_regions_for_good(
        good_type="oil",
        regions=[home_region, occupied_region],
        countries_by_id={
            "proxy-1": WareraCountryCache(
                country_id="proxy-1",
                code="prx",
                name="Proxy",
                production_specialization="oil",
                raw_payload=None,
            ),
            "other-1": WareraCountryCache(
                country_id="other-1",
                code="oth",
                name="Other",
                production_specialization=None,
                raw_payload=None,
            ),
        },
        sanctions_by_id={},
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
        ignored_region_ids=set(),
        ignored_region_deposit_keys=set(),
    )

    assert [region.region_id for region in candidates] == ["P2"]


def test_candidate_regions_include_matching_deposit_regions() -> None:
    specialist_region = build_region(
        "D1",
        country_id="specialist-1",
        initial_country_id="specialist-1",
        resistance=None,
        resistance_max=None,
    )
    deposit_region = WareraRegionCache(
        region_id="D2",
        code="d2",
        name="Deposit Region",
        country_id="other-1",
        initial_country_id="other-1",
        resistance=None,
        resistance_max=None,
        development=10.0,
        strategic_resource=None,
        raw_payload='{"deposit":{"type":"coca","bonusPercent":30}}',
    )

    candidates = RecommendationService._candidate_regions_for_good(
        good_type="coca",
        regions=[specialist_region, deposit_region],
        countries_by_id={
            "specialist-1": WareraCountryCache(
                country_id="specialist-1",
                code="sp",
                name="Specialist",
                production_specialization="coca",
                raw_payload=None,
            ),
            "other-1": WareraCountryCache(
                country_id="other-1",
                code="ot",
                name="Other",
                production_specialization=None,
                raw_payload=None,
            ),
        },
        sanctions_by_id={},
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids=set(),
    )

    assert {region.region_id for region in candidates} == {"D1", "D2"}


def test_recommendation_visibility_includes_limited_sanction_fallback() -> None:
    visible, note = RecommendationService._recommendation_visibility(
        good_type="iron",
        region=build_region(
            "V1",
            country_id="sanctioned-1",
            initial_country_id="holder-1",
            resistance=50,
            resistance_max=100,
        ),
        country=WareraCountryCache(
            country_id="sanctioned-1",
            code="san",
            name="Sanctioned",
            production_specialization="iron",
            raw_payload=None,
        ),
        current_sanction=SanctionedCountry(
            country_id="sanctioned-1",
            country_code="san",
            country_name_snapshot="Sanctioned",
            sanction_level="limited",
            sanction_reason=None,
            created_by=1,
        ),
        source_country=WareraCountryCache(
            country_id="holder-1",
            code="hol",
            name="Holder",
            production_specialization=None,
            raw_payload=None,
        ),
        source_sanction=None,
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids=set(),
    )

    assert visible is True
    assert note == "Highest-resistance occupied territory in limited-sanction Sanctioned."


def test_recommendation_visibility_includes_icpd_aligned_specialist_occupied_region() -> None:
    visible, note = RecommendationService._recommendation_visibility(
        good_type="oil",
        region=build_region(
            "V2",
            country_id="holder-1",
            initial_country_id="proxy-1",
            resistance=50,
            resistance_max=100,
        ),
        country=WareraCountryCache(
            country_id="holder-1",
            code="hol",
            name="Holder",
            production_specialization=None,
            raw_payload=None,
        ),
        current_sanction=None,
        source_country=WareraCountryCache(
            country_id="proxy-1",
            code="prx",
            name="Proxy",
            production_specialization=None,
            raw_payload=None,
        ),
        source_sanction=None,
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    )

    assert visible is True
    assert note == "Occupied territory of ICPD-aligned country Proxy."


def test_recommendation_visibility_hides_plain_specialist_match() -> None:
    visible, note = RecommendationService._recommendation_visibility(
        good_type="steel",
        region=build_region(
            "V3",
            country_id="specialist-1",
            initial_country_id="specialist-1",
            resistance=None,
            resistance_max=None,
        ),
        country=WareraCountryCache(
            country_id="specialist-1",
            code="sp",
            name="Specialist",
            production_specialization="steel",
            raw_payload=None,
        ),
        current_sanction=None,
        source_country=None,
        source_sanction=None,
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids=set(),
    )

    assert visible is False
    assert note == "Country specialization match in Specialist."


def test_ownership_statuses_include_origin_alignment_and_occupied() -> None:
    statuses = RecommendationService._ownership_statuses(
        region=build_region(
            "S1",
            country_id="holder-1",
            initial_country_id="proxy-1",
            resistance=10,
            resistance_max=100,
        ),
        icpd_country_ids=set(),
        proxy_country_ids={"proxy-1"},
        cooperator_country_ids=set(),
    )

    assert statuses == ("proxy", "occupied")


def test_recommendation_entry_can_store_source_country_metadata() -> None:
    entry = RecommendationEntry(
        good_type="grain",
        location_name="Brunei",
        location_code="bn-brunei",
        location_identifier="region-1",
        country_id="holder-1",
        country_name="Vietnam",
        country_code="vn",
        source_country_id="proxy-1",
        source_country_name="Brunei",
        source_country_code="bn",
        ownership_statuses=("proxy", "occupied"),
        production_bonus_percent=60.0,
        deposit_bonus_percent=30.0,
        deposit_ends_at=datetime.now(timezone.utc),
        resistance_display="10 / 10 (40.0% hijacked tax)",
        development=1.0,
        source="automatic",
        note="Occupied territory of ICPD-aligned country Brunei.",
    )

    assert entry.source_country_name == "Brunei"
    assert entry.source_country_code == "bn"


def test_discord_timestamp_uses_unix_epoch() -> None:
    countdown = discord_timestamp(datetime(2026, 4, 21, 15, 2, 10, tzinfo=timezone.utc))

    assert countdown is not None
    assert countdown == "<t:1776783730:R>"


def test_recommendation_sort_key_prefers_higher_resistance_for_occupied_regions() -> None:
    lower_resistance = build_region(
        "R1",
        country_id="holder-1",
        initial_country_id="proxy-1",
        resistance=40,
        resistance_max=100,
        development=50.0,
    )
    higher_resistance = build_region(
        "R2",
        country_id="holder-1",
        initial_country_id="proxy-1",
        resistance=100,
        resistance_max=100,
        development=1.0,
    )

    assert RecommendationService._recommendation_sort_key(
        higher_resistance,
        50.0,
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    ) > RecommendationService._recommendation_sort_key(
        lower_resistance,
        50.0,
        icpd_country_ids=set(),
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    )


def test_recommendation_sort_key_prefers_icpd_over_proxy_for_occupied_regions() -> None:
    proxy_origin = build_region(
        "R3",
        country_id="holder-1",
        initial_country_id="proxy-1",
        resistance=100,
        resistance_max=100,
        development=50.0,
    )
    icpd_origin = build_region(
        "R4",
        country_id="holder-1",
        initial_country_id="icpd-1",
        resistance=50,
        resistance_max=100,
        development=1.0,
    )

    assert RecommendationService._recommendation_sort_key(
        icpd_origin,
        20.5,
        icpd_country_ids={"icpd-1"},
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    ) > RecommendationService._recommendation_sort_key(
        proxy_origin,
        20.5,
        icpd_country_ids={"icpd-1"},
        cooperator_country_ids=set(),
        proxy_country_ids={"proxy-1"},
    )


def test_mysterious_plant_deposit_bonus_outranks_weak_specialist_bonus() -> None:
    specialist_country = WareraCountryCache(
        country_id="specialist-1",
        code="sp",
        name="Specialist",
        production_specialization="coca",
        raw_payload='{"specializedItem":"coca","rankings":{"countryProductionBonus":{"value":5.5}}}',
    )
    deposit_country = WareraCountryCache(
        country_id="deposit-1",
        code="dp",
        name="Deposit Country",
        production_specialization=None,
        raw_payload='{"rulingParty":"party-1"}',
    )
    party = WareraPartyCache(
        party_id="party-1",
        name="Agrarian",
        country_id="deposit-1",
        industrialism=-2,
        raw_payload=None,
    )
    specialist_region = build_region(
        "E1",
        country_id="specialist-1",
        initial_country_id="specialist-1",
        resistance=None,
        resistance_max=None,
        development=1.0,
    )
    specialist_region.raw_payload = "{}"
    deposit_region = WareraRegionCache(
        region_id="E2",
        code="e2",
        name="Deposit Region",
        country_id="deposit-1",
        initial_country_id="deposit-1",
        resistance=None,
        resistance_max=None,
        development=1.0,
        strategic_resource=None,
        raw_payload='{"deposit":{"type":"coca","bonusPercent":30}}',
    )

    specialist_score = RecommendationService._total_production_bonus_percent(
        country=specialist_country,
        region=specialist_region,
        party=None,
        specialization="coca",
    )
    deposit_score = RecommendationService._total_production_bonus_percent(
        country=deposit_country,
        region=deposit_region,
        party=party,
        specialization="coca",
    )

    assert specialist_score == 5.5
    assert deposit_score == 60.0


@pytest.mark.asyncio
async def test_build_recommendations_manual_override_keeps_region_country_and_bonus_metadata() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                WareraCountryCache(
                    country_id="holder-1",
                    code="vn",
                    name="Vietnam",
                    production_specialization=None,
                    raw_payload='{"rulingParty":"party-1"}',
                ),
                WareraCountryCache(
                    country_id="proxy-1",
                    code="bn",
                    name="Brunei",
                    production_specialization="grain",
                    raw_payload=None,
                ),
                WareraPartyCache(
                    party_id="party-1",
                    name="Agrarian",
                    country_id="holder-1",
                    industrialism=-2,
                    raw_payload=None,
                ),
                WareraRegionCache(
                    region_id="region-1",
                    code="bn-brunei",
                    name="Brunei",
                    country_id="holder-1",
                    initial_country_id="proxy-1",
                    resistance=10,
                    resistance_max=10,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload=(
                        '{"deposit":{"type":"grain","bonusPercent":30,'
                        f'"endsAt":"{(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()}"}}'
                    ),
                ),
                LocationRecommendation(
                    guild_id=1,
                    good_type="grain",
                    location_identifier="region-1",
                    location_name_snapshot="Brunei",
                    recommendation_note="Council override",
                    updated_by=123,
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.source == "manual"
    assert entry.location_code == "bn-brunei"
    assert entry.country_id == "holder-1"
    assert entry.country_name == "Vietnam"
    assert entry.country_code == "vn"
    assert entry.source_country_id == "proxy-1"
    assert entry.source_country_name == "Brunei"
    assert entry.source_country_code == "bn"
    assert entry.production_bonus_percent == 60.0
    assert entry.deposit_bonus_percent == 30.0
    assert entry.deposit_ends_at is not None
    assert entry.resistance_display == "10 / 10 (40.0% hijacked tax)"
    assert entry.ownership_statuses == ("manual", "proxy", "occupied")


@pytest.mark.asyncio
async def test_build_recommendations_hides_lower_signal_pick_when_neutral_deposit_has_higher_bonus() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                IcpdProxy(
                    country_id="proxy-1",
                    country_code="pr",
                    country_name_snapshot="Proxy",
                    overlord_country_id="icpd-1",
                    overlord_country_name_snapshot="ICPD",
                    created_by=1,
                ),
                WareraCountryCache(
                    country_id="proxy-1",
                    code="pr",
                    name="Proxy",
                    production_specialization="oil",
                    raw_payload='{"specializedItem":"oil","rankings":{"countryProductionBonus":{"value":20}}}',
                ),
                WareraCountryCache(
                    country_id="holder-1",
                    code="ho",
                    name="Holder",
                    production_specialization=None,
                    raw_payload=None,
                ),
                WareraCountryCache(
                    country_id="neutral-1",
                    code="ne",
                    name="Neutral",
                    production_specialization=None,
                    raw_payload='{"rulingParty":"party-1"}',
                ),
                WareraPartyCache(
                    party_id="party-1",
                    name="Agrarian",
                    country_id="neutral-1",
                    industrialism=-2,
                    raw_payload=None,
                ),
                WareraRegionCache(
                    region_id="occupied-1",
                    code="occ-1",
                    name="Occupied",
                    country_id="holder-1",
                    initial_country_id="proxy-1",
                    resistance=40,
                    resistance_max=100,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload="{}",
                ),
                WareraRegionCache(
                    region_id="deposit-1",
                    code="dep-1",
                    name="Deposit",
                    country_id="neutral-1",
                    initial_country_id="neutral-1",
                    resistance=None,
                    resistance_max=None,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload='{"deposit":{"type":"oil","bonusPercent":30}}',
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert entries == []


@pytest.mark.asyncio
async def test_build_recommendations_keeps_signal_pick_when_it_has_highest_bonus() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                IcpdProxy(
                    country_id="proxy-1",
                    country_code="pr",
                    country_name_snapshot="Proxy",
                    overlord_country_id="icpd-1",
                    overlord_country_name_snapshot="ICPD",
                    created_by=1,
                ),
                WareraCountryCache(
                    country_id="proxy-1",
                    code="pr",
                    name="Proxy",
                    production_specialization="oil",
                    raw_payload='{"specializedItem":"oil","rankings":{"countryProductionBonus":{"value":70}}}',
                ),
                WareraCountryCache(
                    country_id="holder-1",
                    code="ho",
                    name="Holder",
                    production_specialization=None,
                    raw_payload=None,
                ),
                WareraCountryCache(
                    country_id="neutral-1",
                    code="ne",
                    name="Neutral",
                    production_specialization=None,
                    raw_payload='{"rulingParty":"party-1"}',
                ),
                WareraPartyCache(
                    party_id="party-1",
                    name="Agrarian",
                    country_id="neutral-1",
                    industrialism=-2,
                    raw_payload=None,
                ),
                WareraRegionCache(
                    region_id="occupied-1",
                    code="occ-1",
                    name="Occupied",
                    country_id="holder-1",
                    initial_country_id="proxy-1",
                    resistance=40,
                    resistance_max=100,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload="{}",
                ),
                WareraRegionCache(
                    region_id="deposit-1",
                    code="dep-1",
                    name="Deposit",
                    country_id="neutral-1",
                    initial_country_id="neutral-1",
                    resistance=None,
                    resistance_max=None,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload='{"deposit":{"type":"oil","bonusPercent":30}}',
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert len(entries) == 1
    assert entries[0].location_identifier == "occupied-1"
    assert entries[0].note == "Occupied territory of ICPD-aligned country Proxy."


@pytest.mark.asyncio
async def test_build_recommendations_skips_ignored_deposit_region() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                WareraCountryCache(
                    country_id="specialist-1",
                    code="sp",
                    name="Specialist",
                    production_specialization="oil",
                    raw_payload='{"specializedItem":"oil","rankings":{"countryProductionBonus":{"value":20}}}',
                ),
                WareraCountryCache(
                    country_id="neutral-1",
                    code="ne",
                    name="Neutral",
                    production_specialization=None,
                    raw_payload='{"rulingParty":"party-1"}',
                ),
                WareraPartyCache(
                    party_id="party-1",
                    name="Agrarian",
                    country_id="neutral-1",
                    industrialism=-2,
                    raw_payload=None,
                ),
                WareraRegionCache(
                    region_id="specialist-1",
                    code="sp-1",
                    name="Specialist Region",
                    country_id="specialist-1",
                    initial_country_id="specialist-1",
                    resistance=None,
                    resistance_max=None,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload="{}",
                ),
                WareraRegionCache(
                    region_id="deposit-1",
                    code="dep-1",
                    name="Deposit",
                    country_id="neutral-1",
                    initial_country_id="neutral-1",
                    resistance=None,
                    resistance_max=None,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload='{"deposit":{"type":"oil","bonusPercent":30}}',
                ),
                IgnoredRecommendationRegion(
                    guild_id=1,
                    region_id="deposit-1",
                    region_name_snapshot="Deposit",
                    note="Depletes too soon",
                    created_by=1,
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert entries == []


@pytest.mark.asyncio
async def test_build_recommendations_ignores_deposit_only_for_matching_region_good() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                WareraCountryCache(
                    country_id="specialist-1",
                    code="sp",
                    name="Specialist",
                    production_specialization="oil",
                    raw_payload='{"specializedItem":"oil","rankings":{"countryProductionBonus":{"value":20}}}',
                ),
                WareraRegionCache(
                    region_id="specialist-1",
                    code="sp-1",
                    name="Specialist Region",
                    country_id="specialist-1",
                    initial_country_id="specialist-1",
                    resistance=None,
                    resistance_max=None,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload='{"deposit":{"type":"oil","bonusPercent":30}}',
                ),
                IgnoredRecommendationDeposit(
                    guild_id=1,
                    region_id="specialist-1",
                    good_type="oil",
                    region_name_snapshot="Specialist Region",
                    note="Ignore short deposit",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                    created_by=1,
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert len(entries) == 1
    assert entries[0].location_identifier == "specialist-1"
    assert entries[0].production_bonus_percent == 20.0
    assert entries[0].deposit_bonus_percent is None


@pytest.mark.asyncio
async def test_build_recommendations_treats_cooperator_proxy_as_cooperator_alignment() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add_all(
            [
                CooperatorProxy(
                    country_id="coop-proxy-1",
                    country_code="cp",
                    country_name_snapshot="Cooperator Proxy",
                    overlord_country_id="coop-owner-1",
                    overlord_country_name_snapshot="Cooperator Owner",
                    created_by=1,
                ),
                WareraCountryCache(
                    country_id="coop-proxy-1",
                    code="cp",
                    name="Cooperator Proxy",
                    production_specialization="oil",
                    raw_payload='{"specializedItem":"oil","rankings":{"countryProductionBonus":{"value":20}}}',
                ),
                WareraCountryCache(
                    country_id="holder-1",
                    code="ho",
                    name="Holder",
                    production_specialization=None,
                    raw_payload=None,
                ),
                WareraRegionCache(
                    region_id="occupied-1",
                    code="occ-1",
                    name="Occupied",
                    country_id="holder-1",
                    initial_country_id="coop-proxy-1",
                    resistance=40,
                    resistance_max=100,
                    development=1.0,
                    strategic_resource=None,
                    raw_payload="{}",
                ),
            ]
        )
        await session.commit()

        entries = await RecommendationService(session).build_recommendations(1)

    await engine.dispose()

    assert len(entries) == 1
    assert entries[0].ownership_statuses == ("cooperator", "occupied")
