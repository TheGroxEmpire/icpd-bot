"""seed requested proxy entries"""

from alembic import op


revision = "20260421_0014"
down_revision = "20260421_0013"
branch_labels = None
depends_on = None


def _insert_icpd_proxy(proxy_id: str, proxy_code: str, proxy_name: str, overlord_id: str, overlord_name: str) -> None:
    op.execute(
        f"""
        INSERT INTO icpd_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        SELECT
            '{proxy_id}',
            '{proxy_code.upper()}',
            '{proxy_name}',
            '{overlord_id}',
            '{overlord_name}',
            0
        WHERE EXISTS (
            SELECT 1 FROM icpd_countries WHERE country_id = '{overlord_id}'
        )
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )


def _insert_cooperator_proxy(proxy_id: str, proxy_code: str, proxy_name: str, overlord_id: str, overlord_name: str) -> None:
    op.execute(
        f"""
        INSERT INTO cooperator_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        SELECT
            '{proxy_id}',
            '{proxy_code.upper()}',
            '{proxy_name}',
            '{overlord_id}',
            '{overlord_name}',
            0
        WHERE EXISTS (
            SELECT 1 FROM cooperator_countries WHERE country_id = '{overlord_id}'
        )
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )


def _insert_hostile_proxy(proxy_id: str, proxy_code: str, proxy_name: str, overlord_id: str, overlord_name: str) -> None:
    op.execute(
        f"""
        INSERT INTO hostile_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        VALUES (
            '{proxy_id}',
            '{proxy_code.upper()}',
            '{proxy_name}',
            '{overlord_id}',
            '{overlord_name}',
            0
        )
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )


def _insert_other_proxy(proxy_id: str, proxy_code: str, proxy_name: str, group_id: str, group_name: str) -> None:
    op.execute(
        f"""
        INSERT INTO other_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        VALUES (
            '{proxy_id}',
            '{proxy_code.upper()}',
            '{proxy_name}',
            '{group_id}',
            '{group_name}',
            0
        )
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )


def upgrade() -> None:
    # ICPD proxies
    _insert_icpd_proxy("6813b6d446e731854c7ac7f5", "al", "Albania", "6813b6d446e731854c7ac7ba", "Serbia")
    _insert_icpd_proxy("6813b6d546e731854c7ac8a9", "cr", "Costa Rica", "6813b6d546e731854c7ac858", "Venezuela")
    _insert_icpd_proxy("6813b6d546e731854c7ac8b5", "hn", "Honduras", "6813b6d546e731854c7ac858", "Venezuela")
    _insert_icpd_proxy("6813b6d546e731854c7ac8bb", "bz", "Belize", "6813b6d546e731854c7ac858", "Venezuela")
    _insert_icpd_proxy("6873d0ea1758b40e712b5f16", "dj", "Djibouti", "6813b6d446e731854c7ac7b6", "Romania")

    # Hostile proxies
    _insert_hostile_proxy("6813b6d546e731854c7ac87a", "by", "Belarus", "6813b6d446e731854c7ac7ae", "Poland")
    _insert_hostile_proxy("6813b6d546e731854c7ac899", "jm", "Jamaica", "6813b6d446e731854c7ac7e5", "United States")
    _insert_hostile_proxy("6813b6d546e731854c7ac8af", "ni", "Nicaragua", "6813b6d446e731854c7ac7be", "Bulgaria")
    _insert_hostile_proxy("6873d0ea1758b40e712b5f43", "bi", "Burundi", "683ddd2c24b5a2e114af1612", "South Africa")
    _insert_hostile_proxy("6873d0ea1758b40e712b5f59", "sz", "Eswatini", "683ddd2c24b5a2e114af1612", "South Africa")

    # Other proxies with custom labels
    _insert_other_proxy(
        "6813b6d546e731854c7ac8be",
        "tm",
        "Turkmenistan",
        "separatist-non-aligned-p",
        "Separatist/Non-Aligned, 🇵🇱 Poland Enemy",
    )
    _insert_other_proxy(
        "6873d0ea1758b40e712b5f34",
        "ci",
        "Ivory Coast",
        "argentina-separatists",
        "🇦🇷 Argentina Separatists",
    )
    _insert_other_proxy(
        "6813b6d546e731854c7ac8ce",
        "kz",
        "Kazakhstan",
        "separatist-non-aligned",
        "Separatist/Non-Aligned",
    )
    _insert_other_proxy(
        "6873d0ea1758b40e712b5f79",
        "lr",
        "Liberia",
        "uruguay-proxy",
        "🇺🇾 Uruguay Proxy",
    )
    _insert_other_proxy(
        "6873d0ea1758b40e712b5f2e",
        "cf",
        "Central Africa",
        "belgium-separatists",
        "🇧🇪 Belgium Separatists",
    )
    _insert_other_proxy(
        "683ddd2c24b5a2e114af15f7",
        "na",
        "Namibia",
        "rsa-aligned",
        "🇿🇦 RSA Aligned",
    )
    _insert_other_proxy(
        "6873d0ea1758b40e712b5f6d",
        "zw",
        "Zimbabwe",
        "rsa-aligned",
        "🇿🇦 RSA Aligned",
    )

    # Cooperator proxies
    _insert_cooperator_proxy("6873d0ea1758b40e712b5f40", "rw", "Rwanda", "6813b6d546e731854c7ac86e", "Kenya")


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM icpd_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('6813b6d446e731854c7ac7f5', '6813b6d446e731854c7ac7ba'),
            ('6813b6d546e731854c7ac8a9', '6813b6d546e731854c7ac858'),
            ('6813b6d546e731854c7ac8b5', '6813b6d546e731854c7ac858'),
            ('6813b6d546e731854c7ac8bb', '6813b6d546e731854c7ac858'),
            ('6873d0ea1758b40e712b5f16', '6813b6d446e731854c7ac7b6')
        )
        """
    )
    op.execute(
        """
        DELETE FROM hostile_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('6813b6d546e731854c7ac87a', '6813b6d446e731854c7ac7ae'),
            ('6813b6d546e731854c7ac899', '6813b6d446e731854c7ac7e5'),
            ('6813b6d546e731854c7ac8af', '6813b6d446e731854c7ac7be'),
            ('6873d0ea1758b40e712b5f43', '683ddd2c24b5a2e114af1612'),
            ('6873d0ea1758b40e712b5f59', '683ddd2c24b5a2e114af1612')
        )
        """
    )
    op.execute(
        """
        DELETE FROM other_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('6813b6d546e731854c7ac8be', 'separatist-non-aligned-p'),
            ('6873d0ea1758b40e712b5f34', 'argentina-separatists'),
            ('6813b6d546e731854c7ac8ce', 'separatist-non-aligned'),
            ('6873d0ea1758b40e712b5f79', 'uruguay-proxy'),
            ('6873d0ea1758b40e712b5f2e', 'belgium-separatists'),
            ('683ddd2c24b5a2e114af15f7', 'rsa-aligned'),
            ('6873d0ea1758b40e712b5f6d', 'rsa-aligned')
        )
        """
    )
    op.execute(
        """
        DELETE FROM cooperator_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('6873d0ea1758b40e712b5f40', '6813b6d546e731854c7ac86e')
        )
        """
    )
