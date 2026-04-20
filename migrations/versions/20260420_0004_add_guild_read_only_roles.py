"""add guild read only roles"""

from alembic import op
import sqlalchemy as sa


revision = "20260420_0004"
down_revision = "20260419_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_read_only_roles",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_config.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "role_id"),
    )


def downgrade() -> None:
    op.drop_table("guild_read_only_roles")
