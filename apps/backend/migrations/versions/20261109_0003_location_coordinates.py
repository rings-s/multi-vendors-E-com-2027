"""Map coordinates for merchant locations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("merchant_addresses", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("merchant_addresses", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_check_constraint(
        "ck_merchant_addresses_pin",
        "merchant_addresses",
        "(latitude IS NULL) = (longitude IS NULL)"
        " AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
        " AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_merchant_addresses_pin", "merchant_addresses", type_="check")
    op.drop_column("merchant_addresses", "longitude")
    op.drop_column("merchant_addresses", "latitude")
