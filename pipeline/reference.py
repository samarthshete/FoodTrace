"""Build the `additives` table from the Open Food Facts additives taxonomy (specs/003).

Usage: uv run python -m pipeline.reference [--refresh]
US status comes from FDA's Substances Added to Food inventory (specs/013). EFSA's
OpenFoodTox is not imported (CC BY-ND); ADIs come from the taxonomy.
"""

import argparse
import asyncio
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

import httpx
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Additive
from app.db.session import make_engine, make_sessionmaker
from app.settings import get_settings
from pipeline import fda_status

TAXONOMY_URL = "https://static.openfoodfacts.org/data/taxonomies/additives.json"
CACHE = Path("data/reference/additives.json")
RISK_LEVELS = {"en:high": 3, "en:moderate": 2, "en:no": 0}


def _en(entry: dict[str, Any], key: str) -> str | None:
    """Taxonomy properties are keyed by language: {"en": "..."}."""
    value = entry.get(key, {})
    return value.get("en") if isinstance(value, dict) else None


def _adi(raw: str | None) -> Decimal | None:
    try:
        return Decimal(raw) if raw else None
    except InvalidOperation:
        return None


def parse_entry(tag: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Map one taxonomy entry to an `additives` row (mapping table in specs/003)."""
    risk_raw = _en(entry, "efsa_evaluation_overexposure_risk")
    has_evaluation = _en(entry, "efsa_evaluation") is not None
    if risk_raw in RISK_LEVELS:
        grade = "A"
    elif has_evaluation:
        grade = "B"
    else:
        grade = "C"
    names = entry.get("name", {})
    return {
        "code": tag.split(":", 1)[-1],
        "name": names.get("en") or names.get("xx") or tag,
        "class": _en(entry, "additives_classes"),
        "risk_level": RISK_LEVELS.get(risk_raw or ""),
        "evidence_grade": grade,
        "adi_mg_kg": _adi(_en(entry, "efsa_evaluation_adi")),
        "efsa_url": _en(entry, "efsa_evaluation_url"),
        "overexposure_risk": risk_raw,
    }


def load_taxonomy(path: Path = CACHE) -> dict[str, Any]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": get_settings().user_agent}
        resp = httpx.get(TAXONOMY_URL, headers=headers, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    data: dict[str, Any] = json.loads(path.read_text())
    return data


async def upsert(rows: list[dict[str, Any]], database_url: str) -> None:
    engine = make_engine(database_url)
    async with make_sessionmaker(engine)() as session:
        stmt = insert(cast(Table, Additive.__table__)).values(rows)
        update_cols = {c: stmt.excluded[c] for c in rows[0] if c != "code"}
        await session.execute(stmt.on_conflict_do_update(index_elements=["code"], set_=update_cols))
        await session.commit()
    await engine.dispose()


def add_us_status(rows: list[dict[str, Any]], index: dict[str, fda_status.UsStatus]) -> int:
    """Set us_status and fda_cfr_ref from the FDA inventory by name (FDA-3). Returns matches."""
    matched = 0
    for row in rows:
        status = index.get(fda_status.additive_name(row["name"]))
        row["us_status"] = status.status if status else None
        row["fda_cfr_ref"] = status.cfr_ref if status else None
        matched += status is not None
    return matched


def us_status_index(
    refresh: bool, user_agent: str, cache: Path = fda_status.CACHE
) -> dict[str, fda_status.UsStatus] | None:
    """The FDA index, or None if FDA is unavailable (FDA-7). None leaves stored statuses alone,
    because rows without us_status/fda_cfr_ref don't update those columns."""
    try:
        if refresh or not cache.exists():
            fda_status.download(user_agent, cache)
        return fda_status.load(cache)
    except fda_status.FDAUnavailable as exc:
        print(f"warning: FDA inventory unavailable ({exc}); existing US statuses are unchanged")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-download the FDA inventory")
    args = parser.parse_args()
    settings = get_settings()
    rows = [parse_entry(tag, entry) for tag, entry in load_taxonomy().items()]
    index = us_status_index(args.refresh, settings.user_agent)
    us = add_us_status(rows, index) if index is not None else 0
    asyncio.run(upsert(rows, settings.database_url))
    rated = sum(1 for r in rows if r["risk_level"] is not None)
    print(f"additives: {len(rows)} loaded, {rated} with an EFSA overexposure rating, "
          f"{us} with a US status (FDA)")  # FDA-4  # fmt: skip


if __name__ == "__main__":
    main()
