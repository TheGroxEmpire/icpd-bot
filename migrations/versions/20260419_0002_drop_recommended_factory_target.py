"""drop recommended factory target"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0002"
down_revision = "20260419_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("location_recommendations", "recommended_factory_target")


def downgrade() -> None:
    op.add_column(
        "location_recommendations",
        sa.Column("recommended_factory_target", sa.String(length=255), nullable=False, server_default=""),
    )
