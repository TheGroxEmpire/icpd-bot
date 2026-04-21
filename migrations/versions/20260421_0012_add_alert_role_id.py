"""add alert role id"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0012"
down_revision = "20260421_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guild_config", sa.Column("alert_role_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("guild_config", "alert_role_id")
