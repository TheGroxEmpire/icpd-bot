"""add proxy active population alert state"""

import sqlalchemy as sa
from alembic import op

revision = "20260421_0016"
down_revision = "20260421_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy_active_population_alert_state",
        sa.Column("proxy_kind", sa.String(length=32), nullable=False),
        sa.Column("country_id", sa.String(length=24), nullable=False),
        sa.Column("is_below_threshold", sa.Boolean(), nullable=False),
        sa.Column("last_active_population", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("proxy_kind", "country_id"),
    )


def downgrade() -> None:
    op.drop_table("proxy_active_population_alert_state")
