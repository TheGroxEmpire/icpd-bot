"""add hostile proxies"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0008"
down_revision = "20260421_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hostile_proxies",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("overlord_country_id", sa.String(length=24), nullable=False),
        sa.Column("overlord_country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["overlord_country_id"], ["sanctioned_countries.country_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("country_id", "overlord_country_id"),
    )
    op.create_index("ix_hostile_proxies_country_code", "hostile_proxies", ["country_code"])


def downgrade() -> None:
    op.drop_index("ix_hostile_proxies_country_code", table_name="hostile_proxies")
    op.drop_table("hostile_proxies")
