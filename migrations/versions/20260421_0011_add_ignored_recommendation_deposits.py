"""add ignored recommendation deposits"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0011"
down_revision = "20260421_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ignored_recommendation_deposits",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("region_id", sa.String(length=24), nullable=False),
        sa.Column("good_type", sa.String(length=128), nullable=False),
        sa.Column("region_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_config.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "region_id", "good_type"),
    )


def downgrade() -> None:
    op.drop_table("ignored_recommendation_deposits")
