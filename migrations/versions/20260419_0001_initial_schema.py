"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_config",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("council_role_id", sa.BigInteger(), nullable=False),
        sa.Column("default_refresh_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("alert_channel_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("guild_id"),
    )

    op.create_table(
        "icpd_countries",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("country_id"),
    )
    op.create_index("ix_icpd_countries_country_code", "icpd_countries", ["country_code"])

    op.create_table(
        "sanctioned_countries",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("sanction_level", sa.String(length=32), nullable=False),
        sa.Column("sanction_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("country_id"),
    )
    op.create_index("ix_sanctioned_countries_country_code", "sanctioned_countries", ["country_code"])

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

    op.create_table(
        "location_recommendations",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("location_identifier", sa.String(length=64), nullable=False),
        sa.Column("good_type", sa.String(length=128), nullable=False),
        sa.Column("location_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("recommendation_note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_config.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "location_identifier", "good_type"),
    )

    op.create_table(
        "specialization_alert_state",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("last_known_specialization_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("last_alerted_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("country_id"),
    )

    op.create_table(
        "active_region_lists",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_config.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
    )

    op.create_table(
        "warera_country_cache",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("production_specialization", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("country_id"),
    )
    op.create_index("ix_warera_country_cache_code", "warera_country_cache", ["code"])

    op.create_table(
        "warera_region_cache",
        sa.Column("region_id", sa.String(length=24), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("initial_country_id", sa.String(length=24), nullable=True),
        sa.Column("resistance", sa.Integer(), nullable=True),
        sa.Column("resistance_max", sa.Integer(), nullable=True),
        sa.Column("development", sa.Float(), nullable=True),
        sa.Column("strategic_resource", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("region_id"),
    )
    op.create_index("ix_warera_region_cache_code", "warera_region_cache", ["code"])
    op.create_index("ix_warera_region_cache_country_id", "warera_region_cache", ["country_id"])

    op.create_table(
        "sync_state",
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("row_counts", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("job_name"),
    )

    op.execute("INSERT INTO sync_state (job_name) VALUES ('warera_sync')")


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_index("ix_warera_region_cache_country_id", table_name="warera_region_cache")
    op.drop_index("ix_warera_region_cache_code", table_name="warera_region_cache")
    op.drop_table("warera_region_cache")
    op.drop_index("ix_warera_country_cache_code", table_name="warera_country_cache")
    op.drop_table("warera_country_cache")
    op.drop_table("active_region_lists")
    op.drop_table("specialization_alert_state")
    op.drop_table("location_recommendations")
    op.drop_index("ix_icpd_proxies_country_code", table_name="icpd_proxies")
    op.drop_table("icpd_proxies")
    op.drop_index("ix_sanctioned_countries_country_code", table_name="sanctioned_countries")
    op.drop_table("sanctioned_countries")
    op.drop_index("ix_icpd_countries_country_code", table_name="icpd_countries")
    op.drop_table("icpd_countries")
    op.drop_table("guild_config")
