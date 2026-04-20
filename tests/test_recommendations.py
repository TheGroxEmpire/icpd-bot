from icpd_bot.db.models import SanctionedCountry, WareraCountryCache, WareraRegionCache
from icpd_bot.services.recommendations import RecommendationService


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


def test_limited_sanction_fallback_prefers_icpd_aligned_occupied_regions() -> None:
    occupied_by_icpd = build_region(
        "A1",
        country_id="icpd-1",
        initial_country_id="sanctioned-1",
        resistance=10,
        resistance_max=100,
    )
    occupied_by_other = build_region(
        "A2",
        country_id="other-1",
        initial_country_id="sanctioned-1",
        resistance=80,
        resistance_max=100,
    )

    regions = RecommendationService._limited_sanction_occupied_regions(
        country_id="sanctioned-1",
        regions=[occupied_by_icpd, occupied_by_other],
        icpd_country_ids={"icpd-1"},
        proxy_country_ids=set(),
    )

    assert [region.region_id for region in regions] == ["A1"]


def test_limited_sanction_fallback_uses_highest_resistance_when_no_icpd_alignment() -> None:
    low_resistance = build_region(
        "B1",
        country_id="other-1",
        initial_country_id="sanctioned-1",
        resistance=10,
        resistance_max=100,
        development=5.0,
    )
    high_resistance = build_region(
        "B2",
        country_id="other-2",
        initial_country_id="sanctioned-1",
        resistance=60,
        resistance_max=100,
        development=1.0,
    )
    best_ratio = build_region(
        "B3",
        country_id="other-3",
        initial_country_id="sanctioned-1",
        resistance=50,
        resistance_max=60,
        development=0.0,
    )

    regions = RecommendationService._limited_sanction_occupied_regions(
        country_id="sanctioned-1",
        regions=[low_resistance, high_resistance, best_ratio],
        icpd_country_ids=set(),
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
        country_id="other-1",
        initial_country_id="sanctioned-1",
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
        proxy_country_ids=set(),
    )

    assert [region.region_id for region in candidates] == ["C2"]
