"""Layered product lookup: Postgres cache -> Open Food Facts live (specs/006)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import Table, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Additive, Product, ProductAdditive, Score
from app.scoring.config import ScoringConfig
from app.scoring.engine import ScoreResult, score
from app.scoring.ingredients import find_additive_codes
from app.scoring.types import AdditiveInfo, Nutrient, ProductFacts
from app.services.gtin import lookup_forms
from app.services.off_client import OFFClient, SourceUnavailable
from app.services.off_mapping import additive_codes, completeness, map_product
from app.services.usda_client import USDAClient
from app.services.usda_mapping import map_product as map_usda_product


class ProductNotFound(Exception):
    pass


@dataclass(frozen=True)
class LookupResult:
    product: Product
    score: dict[str, Any]  # engine output (spec 005 contract), with breakdown
    stale: bool


def is_fresh(product: Product, now: datetime, cache_days: int) -> bool:
    return now - product.fetched_at < timedelta(days=cache_days)


async def upsert_product(
    session: AsyncSession, row: dict[str, Any], codes: list[str] | None, engine_version: str
) -> None:
    stmt = insert(Product).values(**row)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["gtin"], set_={k: stmt.excluded[k] for k in row if k != "gtin"}
        )
    )
    await session.execute(delete(ProductAdditive).where(ProductAdditive.gtin == row["gtin"]))
    if codes:
        # Codes missing from the reference table get a stub row so the FK holds (ADD-3).
        await session.execute(
            insert(cast(Table, Additive.__table__))
            .values([{"code": c, "name": c.upper()} for c in codes])
            .on_conflict_do_nothing(index_elements=["code"])
        )
        await session.execute(
            insert(ProductAdditive).values(
                [{"gtin": row["gtin"], "additive_code": c} for c in codes]
            )
        )
    # Refreshed data invalidates this version's score; it is recomputed below. Rows for
    # other engine versions are left alone (scores are never rewritten across versions).
    await session.execute(
        delete(Score).where(Score.gtin == row["gtin"], Score.engine_version == engine_version)
    )


async def _facts(session: AsyncSession, product: Product) -> ProductFacts:
    additives: tuple[AdditiveInfo, ...] | None = None
    if product.additives_known:
        rows = await session.scalars(
            select(Additive)
            .join(ProductAdditive, ProductAdditive.additive_code == Additive.code)
            .where(ProductAdditive.gtin == product.gtin)
            .order_by(Additive.code)
        )
        additives = tuple(
            AdditiveInfo(a.code, a.name, a.risk_level, a.evidence_grade, a.efsa_url) for a in rows
        )
    return build_facts(
        product.nutrition, product.categories, product.nova_group, additives,
        product.ingredients_text,
    )  # fmt: skip


async def _derive_additives(session: AsyncSession, row: dict[str, Any]) -> list[str] | None:
    """Additives named in a USDA ingredient list, or None without one (EST-5)."""
    if not row["ingredients_text"]:
        return None
    names = {c: n for c, n in await session.execute(select(Additive.code, Additive.name))}
    codes = find_additive_codes(row["ingredients_text"], names)
    row["additives_known"] = True
    row["source_by_field"]["additives"] = "derived"
    row["completeness"] = completeness(row["nutrition"], row["nova_group"], True)
    return codes


async def product_additives(session: AsyncSession, gtin: str) -> list[dict[str, Any]]:
    """The product's additives with their US status (FDA-5)."""
    rows = await session.scalars(
        select(Additive)
        .join(ProductAdditive, ProductAdditive.additive_code == Additive.code)
        .where(ProductAdditive.gtin == gtin)
        .order_by(Additive.code)
    )
    return [
        {"code": a.code, "name": a.name, "us_status": a.us_status, "fda_cfr_ref": a.fda_cfr_ref}
        for a in rows
    ]


def build_facts(
    nutrition: dict[str, Any],
    categories: list[str],
    nova_group: int | None,
    additives: tuple[AdditiveInfo, ...] | None,
    ingredients_text: str | None = None,
) -> ProductFacts:
    """Engine input from a `products` row's fields (shared with the bulk loader)."""
    return ProductFacts(
        nutrients={
            k: Nutrient(float(v["value"]), bool(v.get("estimated", False)))
            for k, v in nutrition.items()
        },
        category_tags=tuple(categories),
        nova_group=nova_group,
        additives=additives,
        ingredients_text=ingredients_text,
    )


def score_row(gtin: str, result: ScoreResult, *, with_breakdown: bool) -> dict[str, Any]:
    """A `scores` row. Bulk loads store the result without breakdown lines to save space;
    the lines are filled in the first time the product is viewed (OFF-8)."""
    out = result.to_dict(with_breakdown=with_breakdown)
    pts = {k: c["value"] for k, c in out["components"].items()}
    return {
        "gtin": gtin,
        "engine_version": result.engine_version,
        "total": result.total,
        "nutrition_pts": pts["nutrition"],
        "additive_pts": pts["additives"],
        "processing_pts": pts["processing"],
        "breakdown": out,
    }


async def score_product(
    session: AsyncSession, product: Product, cfg: ScoringConfig
) -> dict[str, Any]:
    """Return the stored score for this engine version, computing it once if absent (LOOKUP-9)."""
    existing = await session.get(Score, (product.gtin, cfg.engine_version))
    if existing is not None and "breakdown" in existing.breakdown:
        return existing.breakdown
    # No row, or a compact bulk row: compute the full result. It is deterministic for this
    # engine_version (ENGINE-4), so completing a compact row never changes its score.
    row = score_row(product.gtin, score(await _facts(session, product), cfg), with_breakdown=True)
    stmt = insert(Score).values(**row)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["gtin", "engine_version"], set_={"breakdown": stmt.excluded.breakdown}
        )
    )
    await session.commit()
    out: dict[str, Any] = row["breakdown"]
    return out


async def lookup(
    session: AsyncSession,
    gtin: str,
    off: OFFClient,
    cfg: ScoringConfig,
    now: datetime,
    cache_days: int,
    usda: USDAClient | None = None,
) -> LookupResult:
    """Raise ProductNotFound or SourceUnavailable; otherwise return product + score."""
    cached = await session.get(Product, gtin)
    if cached is not None and is_fresh(cached, now, cache_days):  # LOOKUP-2
        return LookupResult(cached, await score_product(session, cached, cfg), stale=False)

    try:
        raw = await off.fetch(lookup_forms(gtin))  # LOOKUP-3
    except SourceUnavailable:
        if cached is None:
            raise
        return LookupResult(
            cached, await score_product(session, cached, cfg), stale=True
        )  # LOOKUP-8

    if raw is not None:
        row, codes = map_product(gtin, raw, now), additive_codes(raw)
    else:
        food = await usda.fetch(gtin) if usda is not None else None  # USDA-7
        if food is None:
            raise ProductNotFound(gtin)  # LOOKUP-7, USDA-9
        row = map_usda_product(gtin, food, now)  # USDA-8
        codes = await _derive_additives(session, row)  # EST-5

    await upsert_product(session, row, codes, cfg.engine_version)  # LOOKUP-6
    await session.commit()
    product = await session.get(Product, gtin, populate_existing=True)
    assert product is not None
    return LookupResult(product, await score_product(session, product, cfg), stale=False)
