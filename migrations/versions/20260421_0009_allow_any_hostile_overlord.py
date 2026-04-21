"""allow any hostile proxy overlord"""

from alembic import op


revision = "20260421_0009"
down_revision = "20260421_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "hostile_proxies_overlord_country_id_fkey",
        "hostile_proxies",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "hostile_proxies_overlord_country_id_fkey",
        "hostile_proxies",
        "sanctioned_countries",
        ["overlord_country_id"],
        ["country_id"],
        ondelete="RESTRICT",
    )
