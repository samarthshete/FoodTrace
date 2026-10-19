"""Contributions from label photos (specs/017). No photo and no user id are stored.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contributions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("gtin", sa.Text, nullable=False, index=True),
        sa.Column("user_id", sa.Text),  # set once accounts exist (M5)
        sa.Column("extracted", JSONB, nullable=False),  # the fields the user confirmed
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("shared_with_off", sa.Text),  # null = not requested; "ok" or the error
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("contributions")
