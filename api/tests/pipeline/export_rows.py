"""Rows shaped like the Open Food Facts CSV export, for pipeline tests."""

import gzip
from pathlib import Path
from typing import Any

from pipeline.off_bulk import (
    INT_COLUMNS,
    NUTRIENT_COLUMNS,
    STRING_COLUMNS,
    TAG_COLUMNS,
    TEXT_COLUMNS,
    extract,
)

HEADER = ["code", "url", "countries_tags", *TEXT_COLUMNS[1:], *TAG_COLUMNS, *INT_COLUMNS,
          *NUTRIENT_COLUMNS, *STRING_COLUMNS]  # fmt: skip
SNACK = {
    "energy-kj_100g": "1500", "sugars_100g": "12", "saturated-fat_100g": "2.5",
    "salt_100g": "0.9", "fiber_100g": "4.5", "proteins_100g": "8", "fat_100g": "9",
}  # fmt: skip


def export_row(code: str, **overrides: str) -> dict[str, str]:
    row = {name: "" for name in HEADER}
    row.update({
        "code": code, "url": f"https://world.openfoodfacts.org/product/{code}",
        "countries_tags": "en:canada,en:united-states", "product_name": "Oat Bars",
        "brands": "Acme Foods", "ingredients_text": "Oats, sugar, citric acid",
        "image_url": f"https://images.openfoodfacts.org/images/products/{code}/front_en.12.400.jpg",
        "categories_tags": "en:snacks,en:cereal-bars", "additives_tags": "en:e330",
        "nova_group": "4", "last_modified_t": "1760000000", "unique_scans_n": "100",
        "nutriscore_score": "11", "nutriscore_grade": "d", "allergens": "en:gluten,en:milk",
        "traces_tags": "en:nuts", "ingredients_analysis_tags": "en:non-vegan,en:vegetarian",
        **SNACK,
    })  # fmt: skip
    row.update(overrides)
    return row


def write_export(path: Path, rows: list[dict[str, Any]]) -> Path:
    """A gzipped, tab-separated export like the real one."""
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for row in rows:
            f.write("\t".join(row[h] for h in HEADER) + "\n")
    return path


def write_extract(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    return extract(write_export(tmp_path / "products.csv.gz", rows), tmp_path / "us.parquet")
