"""GIN index on products.categories for alternatives lookups (specs/009, ALT-4).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX products_categories_gin ON products USING gin (categories)")


def downgrade() -> None:
    op.drop_index("products_categories_gin", table_name="products")
