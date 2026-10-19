"""Search products by name or brand (specs/016). Database only: never calls a live source."""

import re
import unicodedata
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_WORD = re.compile(r"[a-z0-9]+")
DEFAULT_LIMIT, MAX_LIMIT = 10, 25

# The tsvector expression matches the products_search_tsv index (migration 0001), and `%`
# uses the products_name_trgm index (pg_trgm, default similarity threshold 0.3).
SEARCH_SQL = text("""
    SELECT p.gtin, p.name, p.brand, p.image_url, s.total, s.breakdown -> 'band' AS band
    FROM products p
    LEFT JOIN scores s ON s.gtin = p.gtin AND s.engine_version = :version
    WHERE to_tsvector('simple', coalesce(p.name, '') || ' ' || coalesce(p.brand, ''))
            @@ to_tsquery('simple', :tsquery)
       OR p.name % :plain
    ORDER BY
      ts_rank(to_tsvector('simple', coalesce(p.name, '') || ' ' || coalesce(p.brand, '')),
              to_tsquery('simple', :tsquery))
        + similarity(coalesce(p.name, ''), :plain) DESC,
      s.total IS NULL, p.name, p.gtin
    LIMIT :limit
""")


def words(q: str) -> list[str]:
    """Lowercase ASCII words of the query; everything else is dropped (SEARCH-5)."""
    ascii_q = unicodedata.normalize("NFKD", q).encode("ascii", "ignore").decode().lower()
    return _WORD.findall(ascii_q)


def clamp_limit(limit: int | None) -> int:  # SEARCH-1
    return DEFAULT_LIMIT if limit is None else max(1, min(MAX_LIMIT, limit))


async def search(
    session: AsyncSession, q: str, limit: int, engine_version: str
) -> list[dict[str, Any]]:
    """Products whose name/brand words start with the query's words, or whose name is
    similar to it, best first (SEARCH-2, SEARCH-4)."""
    found = words(q)
    if not found:
        return []
    params = {"tsquery": " & ".join(f"{w}:*" for w in found), "plain": " ".join(found),
              "limit": limit, "version": engine_version}  # fmt: skip
    rows = await session.execute(SEARCH_SQL, params)
    return [
        {
            "gtin": r.gtin,
            "name": r.name,
            "brand": r.brand,
            "image_url": r.image_url,
            "total": r.total,
            "band": r.band,
        }
        for r in rows
    ]
