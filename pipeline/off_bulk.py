"""Bulk import of US products from the Open Food Facts CSV export (specs/011).

Usage: uv run python -m pipeline.off_bulk [--refresh] [--max-products N]

The export (~1.3 GB gzipped, ~4M products) is downloaded once to data/off/ and streamed row
by row. Only US rows and the columns below are kept, in a small Polars extract
(data/off/us.parquet). Each row is reshaped into the live API's product format and mapped
with the same `map_product` as live lookups (LOOKUP-13), so bulk and live rows match.
"""

import argparse
import asyncio
import csv
import gzip
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from app.services.gtin import InvalidGTIN, normalize
from app.services.off_mapping import additive_codes, map_product
from app.services.usda_mapping import UsdaFood, fill_gaps
from app.settings import get_settings
from pipeline import usda_bulk
from pipeline.load import Item, load_products

EXPORT_URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
EXPORT = Path("data/off/products.csv.gz")
EXTRACT = Path("data/off/us.parquet")
COUNTRY = "en:united-states"
# Columns kept, checked against the export's header on 2026-10-12. Tag columns are
# comma-separated; nutrient columns are per 100 g.
TEXT_COLUMNS = ["code", "product_name", "brands", "ingredients_text", "image_url"]
TAG_COLUMNS = ["categories_tags", "labels_tags", "additives_tags", "allergens", "traces_tags",
               "ingredients_analysis_tags"]  # fmt: skip
INT_COLUMNS = ["nova_group", "last_modified_t", "unique_scans_n", "nutriscore_score"]
NUTRIENT_COLUMNS = [
    "energy-kj_100g", "energy-kcal_100g", "energy_100g", "fat_100g", "saturated-fat_100g",
    "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g", "sodium_100g",
    "fruits-vegetables-legumes_100g",
]  # fmt: skip
STRING_COLUMNS = ["nutriscore_grade"]
REQUIRED = ("energy_kj", "sugars_g", "saturated_fat_g", "salt_g")  # NS-3: needed to score
MAX_PRODUCTS = 100_000  # ~3.6 KB per product with scores and indexes; fits the 450 MB budget


def download(user_agent: str, dest: Path = EXPORT) -> Path:
    """Fetch the export once (OFF-1). Good citizen: one bulk file, not per-product calls."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".part")
    with httpx.stream("GET", EXPORT_URL, headers={"User-Agent": user_agent},
                      follow_redirects=True, timeout=120) as resp:  # fmt: skip
        resp.raise_for_status()
        with partial.open("wb") as f:
            for chunk in resp.iter_bytes(1 << 20):
                f.write(chunk)
    partial.rename(dest)
    return dest


def _int(raw: str) -> int | None:
    try:
        return int(float(raw)) if raw else None
    except ValueError:
        return None


def _float(raw: str) -> float | None:
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _tags(raw: str) -> list[str]:
    return [t for t in raw.split(",") if t]


def extract(source: Path = EXPORT, dest: Path = EXTRACT) -> Path:
    """Stream the export and keep US rows and the needed columns (OFF-1, OFF-2)."""
    csv.field_size_limit(sys.maxsize)
    names = [*TEXT_COLUMNS, *TAG_COLUMNS, *INT_COLUMNS, *NUTRIENT_COLUMNS, *STRING_COLUMNS]
    columns: dict[str, list[Any]] = {c: [] for c in names}
    with gzip.open(source, "rt", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        at = {name: i for i, name in enumerate(header)}
        country = at["countries_tags"]
        for fields in reader:
            if len(fields) != len(header) or COUNTRY not in fields[country].split(","):
                continue
            for c in TEXT_COLUMNS + STRING_COLUMNS:
                columns[c].append(fields[at[c]] or None)
            for c in TAG_COLUMNS:
                columns[c].append(_tags(fields[at[c]]))
            for c in INT_COLUMNS:
                columns[c].append(_int(fields[at[c]]))
            for c in NUTRIENT_COLUMNS:
                columns[c].append(_float(fields[at[c]]))
    schema: dict[str, Any] = {c: pl.String for c in TEXT_COLUMNS + STRING_COLUMNS}
    schema |= {c: pl.List(pl.String) for c in TAG_COLUMNS}
    schema |= {c: pl.Int64 for c in INT_COLUMNS} | {c: pl.Float64 for c in NUTRIENT_COLUMNS}
    dest.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(columns, schema=schema).write_parquet(dest)
    return dest


def to_api_product(row: dict[str, Any]) -> dict[str, Any]:
    """Reshape an extract row into the live API's `product` object (OFF-3)."""
    additives = row["additives_tags"]
    return {
        "code": row["code"],
        "product_name": row["product_name"],
        "brands": row["brands"],
        "categories_tags": row["categories_tags"],
        "image_front_url": row["image_url"],  # OFF-4
        "ingredients_text": row["ingredients_text"],
        "nutriments": {c: row[c] for c in NUTRIENT_COLUMNS if row[c] is not None},
        "nova_group": row["nova_group"],
        "labels_tags": row["labels_tags"],
        "allergens_tags": row.get("allergens") or [],  # ACC-6
        "traces_tags": row.get("traces_tags") or [],
        "ingredients_analysis_tags": row.get("ingredients_analysis_tags") or [],
        # The CSV can't tell "no additives" from "not analysed". Without an ingredient list
        # and without additives, the list is unknown (ADD-6).
        "additives_tags": additives if additives or row["ingredients_text"] else None,
    }


def mapped_rows(
    path: Path,
    now: datetime,
    max_products: int = MAX_PRODUCTS,
    usda: dict[str, UsdaFood] | None = None,
    stats: dict[str, int] | None = None,
) -> list[Item]:
    """Load items for valid, named, scorable products (OFF-5).

    USDA fills missing nutrients first (USDA-5, USDA-6). A duplicate code keeps its latest
    edit. Above `max_products`, the most scanned are kept (OFF-10); the rest are still
    found by live lookup when scanned.
    """
    stats = stats if stats is not None else {}
    df = pl.read_parquet(path).sort("last_modified_t", nulls_last=False)
    seen: dict[str, tuple[int, Item]] = {}
    for row in df.iter_rows(named=True):
        try:
            gtin = normalize(row["code"] or "")
        except InvalidGTIN:
            continue
        product = to_api_product(row)
        if not product["product_name"]:
            continue
        mapped = map_product(gtin, product, now)
        if usda and gtin in usda and (n := fill_gaps(mapped, usda[gtin])):
            stats["usda_fields"] = stats.get("usda_fields", 0) + n
            stats["usda_products"] = stats.get("usda_products", 0) + 1
        if not all(k in mapped["nutrition"] for k in REQUIRED):
            continue
        modified = row["last_modified_t"]
        modified_at = datetime.fromtimestamp(modified, UTC) if modified else None
        seen[gtin] = (row["unique_scans_n"] or 0, (mapped, additive_codes(product), modified_at))
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1][0], kv[0]))
    return [item for _, (_, item) in ranked[:max_products]]


def extract_outdated(extract: Path = EXTRACT, export: Path = EXPORT) -> bool:
    """Rebuild the extract if it's missing, older than the export, or lacks a column we now
    keep (e.g. allergens, added for spec 018)."""
    if not extract.exists():
        return True
    if export.exists() and extract.stat().st_mtime < export.stat().st_mtime:
        return True
    names = [*TEXT_COLUMNS, *TAG_COLUMNS, *INT_COLUMNS, *NUTRIENT_COLUMNS, *STRING_COLUMNS]
    return not set(names) <= set(pl.read_parquet_schema(extract))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download a new export")
    parser.add_argument("--max-products", type=int, default=MAX_PRODUCTS)
    args = parser.parse_args()
    settings = get_settings()
    started = time.monotonic()
    if args.refresh or (not EXPORT.exists() and extract_outdated()):
        download(settings.user_agent)
        print(f"off: export downloaded in {time.monotonic() - started:.0f}s")
    if args.refresh or extract_outdated():
        extract()
        print(f"off: US extract written to {EXTRACT} ({time.monotonic() - started:.0f}s)")
    usda = usda_fill()
    now = datetime.now(UTC)
    stats: dict[str, int] = {}
    rows = mapped_rows(EXTRACT, now, args.max_products, usda, stats)
    if usda:
        print(f"usda: filled {stats.get('usda_fields', 0)} fields in "
              f"{stats.get('usda_products', 0)} products")  # fmt: skip
    print(asyncio.run(load_products(settings.database_url, rows, now)))


def usda_fill() -> dict[str, UsdaFood] | None:
    """USDA gap-fill data if the Branded Foods zip is present (USDA-4), else None."""
    zip_path, cache = usda_bulk.ZIP, usda_bulk.FILL_CACHE
    if not zip_path.exists():
        print(
            f"usda: no {zip_path}; skipping the gap-fill (download from {usda_bulk.DOWNLOAD_PAGE})"
        )
        return None
    if cache.exists() and cache.stat().st_mtime >= max(zip_path.stat().st_mtime,
                                                        EXTRACT.stat().st_mtime):  # fmt: skip
        return usda_bulk.load_fill(cache)
    wanted = set()
    for code in pl.read_parquet(EXTRACT, columns=["code"])["code"]:
        try:
            wanted.add(normalize(code or ""))
        except InvalidGTIN:
            continue
    fill = usda_bulk.read_fill(zip_path, wanted)
    usda_bulk.save_fill(fill, cache)
    return fill


if __name__ == "__main__":
    main()
