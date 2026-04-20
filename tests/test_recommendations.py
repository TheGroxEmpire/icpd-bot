from icpd_bot.db.models import SanctionedCountry, WareraCountryCache, WareraPartyCache, WareraRegionCache
from icpd_bot.services.recommendations import RecommendationEntry, RecommendationService


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
        resistance_display="10 / 10 (40.0% hijacked tax)",
        development=1.0,
        source="automatic",
        note="Occupied territory of ICPD-aligned country Brunei.",
    )

    assert entry.source_country_name == "Brunei"
    assert entry.source_country_code == "bn"


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
