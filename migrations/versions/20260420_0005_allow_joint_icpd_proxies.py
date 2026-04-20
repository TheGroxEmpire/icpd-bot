"""allow joint icpd proxies"""

from alembic import op
import sqlalchemy as sa


revision = "20260420_0005"
down_revision = "20260420_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("icpd_proxies", "icpd_proxies_old")
    op.drop_index("ix_icpd_proxies_country_code", table_name="icpd_proxies_old")
    op.create_table(
        "icpd_proxies",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("overlord_country_id", sa.String(length=24), nullable=False),
        sa.Column("overlord_country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["overlord_country_id"], ["icpd_countries.country_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("country_id", "overlord_country_id"),
    )
    op.create_index("ix_icpd_proxies_country_code", "icpd_proxies", ["country_code"])
    op.execute(
        """
        INSERT INTO icpd_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by,
            created_at
        )
        SELECT
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by,
            created_at
        FROM icpd_proxies_old
        """
    )
    op.drop_table("icpd_proxies_old")


def downgrade() -> None:
    op.rename_table("icpd_proxies", "icpd_proxies_old")
    op.drop_index("ix_icpd_proxies_country_code", table_name="icpd_proxies_old")
    op.create_table(
        "icpd_proxies",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("overlord_country_id", sa.String(length=24), nullable=False),
        sa.Column("overlord_country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["overlord_country_id"], ["icpd_countries.country_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("country_id"),
    )
    op.create_index("ix_icpd_proxies_country_code", "icpd_proxies", ["country_code"])
    op.execute(
        """
        INSERT INTO icpd_proxies (
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by,
            created_at
        )
        SELECT DISTINCT ON (country_id)
            country_id,
            country_code,
            country_name_snapshot,
            overlord_country_id,
            overlord_country_name_snapshot,
            created_by,
            created_at
        FROM icpd_proxies_old
        ORDER BY country_id, created_at
        """
    )
    op.drop_table("icpd_proxies_old")
