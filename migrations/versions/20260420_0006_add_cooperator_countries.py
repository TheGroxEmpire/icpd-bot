"""add cooperator countries"""

from alembic import op
import sqlalchemy as sa


revision = "20260420_0006"
down_revision = "20260420_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cooperator_countries",
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("country_code", sa.String(length=32), nullable=False),
        sa.Column("country_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("country_id"),
    )
    op.create_index("ix_cooperator_countries_country_code", "cooperator_countries", ["country_code"])


def downgrade() -> None:
    op.drop_index("ix_cooperator_countries_country_code", table_name="cooperator_countries")
    op.drop_table("cooperator_countries")
