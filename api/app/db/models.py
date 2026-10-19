"""SQLAlchemy models for SPEC §5. User tables arrive with accounts (M5)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    gtin: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    primary_category: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    image_url: Mapped[str | None] = mapped_column(Text)
    ingredients_text: Mapped[str | None] = mapped_column(Text)
    nutrition: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # per 100 g/ml
    nova_group: Mapped[int | None] = mapped_column(SmallInteger)
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_organic: Mapped[bool] = mapped_column(Boolean, default=False)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)  # ACC-6
    traces: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    ingredients_analysis: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    additives_known: Mapped[bool] = mapped_column(Boolean, default=False)
    source_by_field: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    completeness: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Additive(Base):
    __tablename__ = "additives"

    code: Mapped[str] = mapped_column(Text, primary_key=True)  # e.g. "e250"
    name: Mapped[str] = mapped_column(Text)
    additive_class: Mapped[str | None] = mapped_column("class", Text)
    risk_level: Mapped[int | None] = mapped_column(SmallInteger)
    evidence_grade: Mapped[str | None] = mapped_column(Text)
    adi_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric)
    us_status: Mapped[str | None] = mapped_column(Text)
    efsa_url: Mapped[str | None] = mapped_column(Text)
    fda_cfr_ref: Mapped[str | None] = mapped_column(Text)
    overexposure_risk: Mapped[str | None] = mapped_column(Text)


class ProductAdditive(Base):
    __tablename__ = "product_additives"

    gtin: Mapped[str] = mapped_column(
        Text, ForeignKey("products.gtin", ondelete="CASCADE"), primary_key=True
    )
    additive_code: Mapped[str] = mapped_column(Text, ForeignKey("additives.code"), primary_key=True)


class Score(Base):
    __tablename__ = "scores"

    gtin: Mapped[str] = mapped_column(
        Text, ForeignKey("products.gtin", ondelete="CASCADE"), primary_key=True
    )
    engine_version: Mapped[str] = mapped_column(Text, primary_key=True)
    total: Mapped[int | None] = mapped_column(SmallInteger)
    nutrition_pts: Mapped[Decimal | None] = mapped_column(Numeric)
    additive_pts: Mapped[Decimal | None] = mapped_column(Numeric)
    processing_pts: Mapped[Decimal | None] = mapped_column(Numeric)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB)  # full engine output
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Recall(Base):
    """An openFDA food enforcement record within the window (specs/010, RECALL-2)."""

    __tablename__ = "recalls"
    recall_number: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    classification: Mapped[str | None] = mapped_column(Text)
    recalling_firm: Mapped[str | None] = mapped_column(Text)
    product_description: Mapped[str] = mapped_column(Text, default="")
    code_info: Mapped[str | None] = mapped_column(Text)
    more_code_info: Mapped[str | None] = mapped_column(Text)
    reason_for_recall: Mapped[str | None] = mapped_column(Text)
    recall_initiation_date: Mapped[date | None] = mapped_column(Date)
    report_date: Mapped[date] = mapped_column(Date)
    codes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)  # GTIN-13s (RECALL-3)


class RecallSync(Base):
    """When each recall source was last synced: the data's `as_of` (RECALL-2)."""

    __tablename__ = "recall_sync"
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Contribution(Base):
    """A product added from a label photo (specs/017). Never stores the photo."""

    __tablename__ = "contributions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gtin: Mapped[str] = mapped_column(Text, index=True)
    user_id: Mapped[str | None] = mapped_column(Text)
    extracted: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    shared_with_off: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
