"""adjust seeded proxy entries"""

from alembic import op


revision = "20260421_0015"
down_revision = "20260421_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM hostile_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('683ddd2c24b5a2e114af15f7', '683ddd2c24b5a2e114af1612'),
            ('6873d0ea1758b40e712b5f6d', '683ddd2c24b5a2e114af1612')
        )
        """
    )

    op.execute(
        """
        INSERT INTO other_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        VALUES
            ('683ddd2c24b5a2e114af15f7', 'NA', 'Namibia', 'rsa-aligned', '🇿🇦 RSA Aligned', 0),
            ('6873d0ea1758b40e712b5f6d', 'ZW', 'Zimbabwe', 'rsa-aligned', '🇿🇦 RSA Aligned', 0)
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE other_proxies
        SET overlord_country_name_snapshot = CASE
            WHEN overlord_country_id = 'separatist-non-aligned-p' THEN 'Separatist/Non-Aligned, 🇵🇱 Poland Enemy'
            WHEN overlord_country_id = 'argentina-separatists' THEN '🇦🇷 Argentina Separatists'
            WHEN overlord_country_id = 'separatist-non-aligned' THEN 'Separatist/Non-Aligned'
            WHEN overlord_country_id = 'uruguay-proxy' THEN '🇺🇾 Uruguay Proxy'
            WHEN overlord_country_id = 'belgium-separatists' THEN '🇧🇪 Belgium Separatists'
            WHEN overlord_country_id = 'rsa-aligned' THEN '🇿🇦 RSA Aligned'
            ELSE overlord_country_name_snapshot
        END
        WHERE overlord_country_id IN (
            'separatist-non-aligned-p',
            'argentina-separatists',
            'separatist-non-aligned',
            'uruguay-proxy',
            'belgium-separatists',
            'rsa-aligned'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE other_proxies
        SET overlord_country_name_snapshot = CASE
            WHEN overlord_country_id = 'separatist-non-aligned-p' THEN 'separatist/non-aligned, Poland enemy'
            WHEN overlord_country_id = 'argentina-separatists' THEN 'Argentina separatists'
            WHEN overlord_country_id = 'separatist-non-aligned' THEN 'separatist/non-aligned'
            WHEN overlord_country_id = 'uruguay-proxy' THEN 'Uruguay proxy'
            WHEN overlord_country_id = 'belgium-separatists' THEN 'Belgium separatists'
            ELSE overlord_country_name_snapshot
        END
        WHERE overlord_country_id IN (
            'separatist-non-aligned-p',
            'argentina-separatists',
            'separatist-non-aligned',
            'uruguay-proxy',
            'belgium-separatists'
        )
        """
    )

    op.execute(
        """
        DELETE FROM other_proxies
        WHERE (country_id, overlord_country_id) IN (
            ('683ddd2c24b5a2e114af15f7', 'rsa-aligned'),
            ('6873d0ea1758b40e712b5f6d', 'rsa-aligned')
        )
        """
    )

    op.execute(
        """
        INSERT INTO hostile_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by
        )
        VALUES
            ('683ddd2c24b5a2e114af15f7', 'NA', 'Namibia', '683ddd2c24b5a2e114af1612', 'South Africa', 0),
            ('6873d0ea1758b40e712b5f6d', 'ZW', 'Zimbabwe', '683ddd2c24b5a2e114af1612', 'South Africa', 0)
        ON CONFLICT (country_id, overlord_country_id) DO NOTHING
        """
    )
