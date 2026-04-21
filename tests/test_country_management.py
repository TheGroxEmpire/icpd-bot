from icpd_bot.commands.country_management import build_hostile_proxy_list_embed, build_icpd_proxy_list_embed
from icpd_bot.db.models import HostileProxy, IcpdProxy


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
    )

    assert len(embed.fields) == 1
    assert "active `13`" in embed.fields[0].value


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
