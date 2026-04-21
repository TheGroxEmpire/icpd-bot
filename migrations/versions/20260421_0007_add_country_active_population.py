"""add country active population cache column"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0007"
down_revision = "20260420_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("warera_country_cache", sa.Column("active_population", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("warera_country_cache", "active_population")
