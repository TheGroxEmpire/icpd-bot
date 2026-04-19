"""add warera party cache"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0003"
down_revision = "20260419_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warera_party_cache",
        sa.Column("party_id", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country_id", sa.String(length=24), nullable=True),
        sa.Column("industrialism", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("party_id"),
    )


def downgrade() -> None:
    op.drop_table("warera_party_cache")
