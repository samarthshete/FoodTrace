"""Core product, additive and score tables (SPEC §5, without user tables).

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "products",
        sa.Column("gtin", sa.Text, primary_key=True),
        sa.Column("name", sa.Text),
        sa.Column("brand", sa.Text),
        sa.Column("primary_category", sa.Text),
        sa.Column("categories", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("image_url", sa.Text),
        sa.Column("ingredients_text", sa.Text),
        sa.Column("nutrition", JSONB, nullable=False, server_default="{}"),
        sa.Column("nova_group", sa.SmallInteger),
        sa.Column("labels", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("is_organic", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("additives_known", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source_by_field", JSONB, nullable=False, server_default="{}"),
        sa.Column("completeness", sa.Numeric(3, 2)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("gtin ~ '^[0-9]{13}$'", name="products_gtin_13_digits"),
        sa.CheckConstraint("nova_group BETWEEN 1 AND 4", name="products_nova_range"),
    )
    op.execute("CREATE INDEX products_name_trgm ON products USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX products_brand_trgm ON products USING gin (brand gin_trgm_ops)")
    op.execute(
        "CREATE INDEX products_search_tsv ON products USING gin "
        "(to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(brand, '')))"
    )
    op.create_index("products_primary_category", "products", ["primary_category"])

    op.create_table(
        "additives",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("class", sa.Text),
        sa.Column("risk_level", sa.SmallInteger),
        sa.Column("evidence_grade", sa.Text),
        sa.Column("adi_mg_kg", sa.Numeric),
        sa.Column("us_status", sa.Text),
        sa.Column("efsa_url", sa.Text),
        sa.Column("fda_cfr_ref", sa.Text),
        sa.Column("overexposure_risk", sa.Text),
        sa.CheckConstraint("risk_level BETWEEN 0 AND 3", name="additives_risk_range"),
        sa.CheckConstraint("evidence_grade IN ('A', 'B', 'C')", name="additives_grade"),
    )

    op.create_table(
        "product_additives",
        sa.Column(
            "gtin", sa.Text, sa.ForeignKey("products.gtin", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("additive_code", sa.Text, sa.ForeignKey("additives.code"), primary_key=True),
    )

    op.create_table(
        "scores",
        sa.Column(
            "gtin", sa.Text, sa.ForeignKey("products.gtin", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("engine_version", sa.Text, primary_key=True),
        sa.Column("total", sa.SmallInteger),
        sa.Column("nutrition_pts", sa.Numeric),
        sa.Column("additive_pts", sa.Numeric),
        sa.Column("processing_pts", sa.Numeric),
        sa.Column("breakdown", JSONB, nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("total BETWEEN 0 AND 100", name="scores_total_range"),
    )


def downgrade() -> None:
    op.drop_table("scores")
    op.drop_table("product_additives")
    op.drop_table("additives")
    op.drop_table("products")
