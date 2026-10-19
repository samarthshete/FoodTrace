"""Better-scored products from the same category (specs/009)."""

from typing import Any

from sqlalchemy import Float, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, Score
from app.scoring.config import ScoringConfig


def candidate_categories(primary: str | None, categories: list[str], fallbacks: int) -> list[str]:
    """primary_category, then up to `fallbacks` less specific ones (ALT-4).

    OFF lists categories from general to specific, so less specific means further left.
    """
    if primary is None:
        return []
    if primary in categories:
        broader = categories[: categories.index(primary)][::-1]
    else:
        broader = [c for c in categories[::-1] if c != primary]
    return [primary, *broader[:fallbacks]]


async def _in_category(
    session: AsyncSession,
    category: str,
    base_gtin: str,
    nutri_class: str,
    min_total: int | None,
    cfg: ScoringConfig,
) -> list[dict[str, Any]]:
    data = Score.breakdown
    confidence = data["confidence"].astext.cast(Float)
    stmt = (
        select(
            Product.gtin,
            Product.name,
            Product.brand,
            Product.image_url,
            Score.total,
            data["band"],
            confidence,
        )
        .join(Score, Score.gtin == Product.gtin)
        .where(
            Score.engine_version == cfg.engine_version,
            Product.categories.contains([category]),
            Product.gtin != base_gtin,  # ALT-6
            data["status"].astext == "scored",  # ALT-2
            confidence >= cfg.alternatives.min_confidence,
            data["nutriscore"]["class"].astext == nutri_class,  # ALT-3
        )
        .order_by(Score.total.desc(), confidence.desc(), Product.gtin)  # ALT-6
        .limit(cfg.alternatives.limit)
    )
    if min_total is not None:
        stmt = stmt.where(Score.total >= min_total)  # ALT-5
    rows = await session.execute(stmt)
    return [
        {
            "gtin": gtin,
            "name": name,
            "brand": brand,
            "image_url": image,
            "total": total,
            "band": band,
            "confidence": conf,
        }
        for gtin, name, brand, image, total, band, conf in rows
    ]


async def find_alternatives(
    session: AsyncSession, product: Product, score: dict[str, Any], cfg: ScoringConfig
) -> tuple[str | None, list[dict[str, Any]]]:
    """Return (matched category, alternatives). Empty, never an error (ALT-8)."""
    total = score["total"] if score["status"] == "scored" else None
    min_total = None if total is None else total + cfg.alternatives.min_gain
    nutri_class = score["nutriscore"]["class"]
    for category in candidate_categories(
        product.primary_category, product.categories, cfg.alternatives.fallback_categories
    ):
        found = await _in_category(session, category, product.gtin, nutri_class, min_total, cfg)
        if found:
            return category, found
    return None, []
