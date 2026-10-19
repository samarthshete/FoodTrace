"""Allergens, traces and ingredient analysis on products (specs/018, ACC-6).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
COLUMNS = ("allergens", "traces", "ingredients_analysis")


def upgrade() -> None:
    for name in COLUMNS:  # OFF tags, e.g. en:milk; en:non-vegan
        op.add_column(
            "products", sa.Column(name, ARRAY(sa.Text), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    for name in COLUMNS:
        op.drop_column("products", name)
