"""openFDA recall records and their sync time (specs/010).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recalls",
        sa.Column("recall_number", sa.Text, primary_key=True),
        sa.Column("event_id", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("classification", sa.Text),
        sa.Column("recalling_firm", sa.Text),
        sa.Column("product_description", sa.Text, nullable=False, server_default=""),
        sa.Column("code_info", sa.Text),
        sa.Column("more_code_info", sa.Text),
        sa.Column("reason_for_recall", sa.Text),
        sa.Column("recall_initiation_date", sa.Date),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("codes", ARRAY(sa.Text), nullable=False, server_default="{}"),
    )
    op.execute("CREATE INDEX recalls_codes_gin ON recalls USING gin (codes)")
    op.create_table(
        "recall_sync",
        sa.Column("source", sa.Text, primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recall_sync")
    op.drop_table("recalls")
