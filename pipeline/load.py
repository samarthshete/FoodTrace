"""Load bulk product rows into Postgres and score them (specs/011, OFF-6..OFF-10).

Rows are COPYed into a temporary staging table and merged into `products` in one
transaction. A row already in the table is only replaced when the bulk data is newer than
when we last fetched it, so a fresh live lookup is never overwritten by an older export.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.session import make_engine
from app.scoring.config import ScoringConfig, default_config
from app.scoring.engine import score
from app.scoring.types import AdditiveInfo
from app.services.lookup import build_facts, score_row

MAX_DB_MB = 450  # Supabase free tier is 500 MB; keep headroom (SPEC §2)
COLUMNS = [
    "gtin", "name", "brand", "primary_category", "categories", "image_url", "ingredients_text",
    "nutrition", "nova_group", "labels", "is_organic", "additives_known", "source_by_field",
    "completeness", "fetched_at", "allergens", "traces", "ingredients_analysis",
]  # fmt: skip

# (products row, additive codes or None, when the source last changed the product)
Item = tuple[dict[str, Any], list[str] | None, datetime | None]


class DatabaseTooLarge(Exception):
    pass


@dataclass(frozen=True)
class LoadReport:
    offered: int
    written: int
    kept_newer: int
    scored: int
    db_mb: float

    def __str__(self) -> str:
        return (
            f"load: {self.offered} products offered, {self.written} written, "
            f"{self.kept_newer} kept (our copy was newer), {self.scored} scored; "
            f"database {self.db_mb:.0f} MB of {MAX_DB_MB} MB"
        )


def _record(row: dict[str, Any], modified_at: datetime | None) -> tuple[Any, ...]:
    values = [row[c] for c in COLUMNS]
    for i, c in enumerate(COLUMNS):
        if c in ("nutrition", "source_by_field"):
            values[i] = json.dumps(values[i])  # asyncpg's COPY wants JSONB as text
    return (*values, modified_at)


async def _copy_to_staging(conn: AsyncConnection, records: list[tuple[Any, ...]]) -> None:
    await conn.execute(text(
        "CREATE TEMP TABLE staging_products (LIKE products INCLUDING DEFAULTS, "
        "modified_at TIMESTAMPTZ) ON COMMIT DROP"
    ))  # fmt: skip
    raw = await conn.get_raw_connection()
    await raw.driver_connection.copy_records_to_table(  # type: ignore[union-attr]
        "staging_products", records=records, columns=[*COLUMNS, "modified_at"]
    )


async def _merge(conn: AsyncConnection) -> int:
    """Insert new rows; replace existing ones unless ours is newer (OFF-6). Returns writes."""
    await conn.execute(text(
        "DELETE FROM staging_products s USING products p "
        "WHERE p.gtin = s.gtin AND s.modified_at IS NOT NULL AND p.fetched_at >= s.modified_at"
    ))  # fmt: skip
    cols = ", ".join(COLUMNS)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS if c != "gtin")
    await conn.execute(text(
        f"INSERT INTO products ({cols}) SELECT {cols} FROM staging_products "
        f"ON CONFLICT (gtin) DO UPDATE SET {updates}"
    ))  # fmt: skip
    await conn.execute(text(
        "CREATE TEMP TABLE touched ON COMMIT DROP AS SELECT gtin FROM staging_products"
    ))  # fmt: skip
    await conn.execute(text("ALTER TABLE touched ADD PRIMARY KEY (gtin)"))
    written = await conn.scalar(text("SELECT count(*) FROM touched"))
    return int(written or 0)


async def _replace_additives(conn: AsyncConnection, items: list[Item]) -> None:
    """Additive links for every written product (OFF-7). Unknown codes get a stub row."""
    await conn.execute(text(
        "DELETE FROM product_additives pa USING touched t WHERE pa.gtin = t.gtin"
    ))  # fmt: skip
    touched = set(await conn.scalars(text("SELECT gtin FROM touched")))
    links = [(r["gtin"], c) for r, codes, _ in items if r["gtin"] in touched for c in codes or []]
    if not links:
        return
    codes = sorted({c for _, c in links})
    await conn.execute(
        text(
            "INSERT INTO additives (code, name) "
            "SELECT c, upper(c) FROM unnest(CAST(:codes AS text[])) c ON CONFLICT (code) DO NOTHING"
        ),
        {"codes": codes},
    )
    raw = await conn.get_raw_connection()
    await raw.driver_connection.copy_records_to_table(  # type: ignore[union-attr]
        "product_additives", records=links, columns=["gtin", "additive_code"]
    )


async def _additive_info(conn: AsyncConnection) -> dict[str, AdditiveInfo]:
    rows = await conn.execute(
        text("SELECT code, name, risk_level, evidence_grade, efsa_url FROM additives")
    )
    return {r.code: AdditiveInfo(r.code, r.name, r.risk_level, r.evidence_grade, r.efsa_url)
            for r in rows}  # fmt: skip


async def _score(conn: AsyncConnection, items: list[Item], cfg: ScoringConfig) -> int:
    """Score written products, and any without a current-version score, compactly (OFF-8)."""
    version = {"v": cfg.engine_version}
    await conn.execute(
        text(
            "DELETE FROM scores s USING touched t WHERE s.gtin = t.gtin AND s.engine_version = :v"
        ),
        version,
    )
    scored = set(
        await conn.scalars(text("SELECT gtin FROM scores WHERE engine_version = :v"), version)
    )
    info = await _additive_info(conn)
    records = []
    for row, codes, _ in items:
        if row["gtin"] in scored:
            continue
        additives = None if codes is None else tuple(info[c] for c in sorted(codes))
        facts = build_facts(row["nutrition"], row["categories"], row["nova_group"], additives,
                            row["ingredients_text"])  # fmt: skip
        out = score_row(row["gtin"], score(facts, cfg), with_breakdown=False)
        records.append((
            out["gtin"], out["engine_version"], out["total"], _num(out["nutrition_pts"]),
            _num(out["additive_pts"]), _num(out["processing_pts"]), json.dumps(out["breakdown"]),
        ))  # fmt: skip
    raw = await conn.get_raw_connection()
    await raw.driver_connection.copy_records_to_table(  # type: ignore[union-attr]
        "scores", records=records,
        columns=["gtin", "engine_version", "total", "nutrition_pts", "additive_pts",
                 "processing_pts", "breakdown"],
    )  # fmt: skip
    return len(records)


def _num(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


async def load_products(
    database_url: str,
    items: list[Item],
    now: datetime,
    cfg: ScoringConfig | None = None,
    max_mb: float = MAX_DB_MB,
) -> LoadReport:
    """Merge, link additives, score, and check the size, all in one transaction (OFF-9)."""
    cfg = cfg or default_config()
    engine = make_engine(database_url)
    try:
        async with engine.begin() as conn:
            await _copy_to_staging(conn, [_record(r, m) for r, _, m in items])
            written = await _merge(conn)
            await _replace_additives(conn, items)
            scored = await _score(conn, items, cfg)
            size = await conn.scalar(text("SELECT pg_database_size(current_database())"))
            db_mb = int(size or 0) / 1024 / 1024
            if db_mb > max_mb:  # raising rolls the whole load back
                raise DatabaseTooLarge(f"database would be {db_mb:.0f} MB (limit {max_mb} MB)")
    finally:
        await engine.dispose()
    return LoadReport(len(items), written, len(items) - written, scored, db_mb)
