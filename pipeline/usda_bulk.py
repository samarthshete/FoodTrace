"""USDA Branded Foods gap-fill for the bulk import (specs/012, USDA-4..6).

The FoodData Central zip (~450 MB, ~3 GB unpacked) is read in place: each CSV member is
streamed straight out of the zip, so nothing is unpacked to disk. Only GTINs that are in
the Open Food Facts US extract are kept. The result is cached in data/usda/fill.json.gz.
"""

import csv
import gzip
import io
import json
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

from app.services.gtin import InvalidGTIN, normalize
from app.services.usda_mapping import NUTRIENT_IDS, UsdaFood, category_map, to_number

ZIP = Path("data/usda/branded.zip")
FILL_CACHE = Path("data/usda/fill.json.gz")
DOWNLOAD_PAGE = "https://fdc.nal.usda.gov/download-datasets/"


def gtin_of(raw: str) -> str | None:
    """USDA stores GTINs with up to 14 digits and extra leading zeros."""
    digits = raw.strip().lstrip("0")
    if not digits.isdigit():
        return None
    try:
        return normalize(digits.zfill(12))
    except InvalidGTIN:
        return None


def _rows(z: zipfile.ZipFile, name: str) -> Iterator[list[str]]:
    member = next(n for n in z.namelist() if n.rsplit("/", 1)[-1] == name)
    with z.open(member) as raw:
        yield from csv.reader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))


def read_fill(zip_path: Path, wanted: set[str]) -> dict[str, UsdaFood]:
    """USDA data for the wanted GTINs, the latest record per GTIN (USDA-4)."""
    csv.field_size_limit(sys.maxsize)
    cats = category_map()
    z = zipfile.ZipFile(zip_path)

    branded = _rows(z, "branded_food.csv")
    at = {c: i for i, c in enumerate(next(branded))}
    best: dict[str, tuple[str, int, list[str]]] = {}  # gtin -> (available_date, fdc_id, row)
    for row in branded:
        if row[at["discontinued_date"]] or row[at["market_country"]] not in ("United States", ""):
            continue
        gtin = gtin_of(row[at["gtin_upc"]])
        if gtin is None or gtin not in wanted or cats.is_excluded(row[at["branded_food_category"]]):
            continue
        key = (row[at["available_date"]], int(row[at["fdc_id"]]), row)
        if gtin not in best or key[:2] > best[gtin][:2]:
            best[gtin] = key
    by_fdc = {str(fdc): gtin for gtin, (_, fdc, _) in best.items()}

    descriptions: dict[str, str] = {}
    foods = _rows(z, "food.csv")
    fat = {c: i for i, c in enumerate(next(foods))}
    for row in foods:
        if row[fat["fdc_id"]] in by_fdc:
            descriptions[row[fat["fdc_id"]]] = row[fat["description"]]

    nutrients: dict[str, dict[int, float]] = {}
    ids = {str(i) for i in NUTRIENT_IDS}
    rows = _rows(z, "food_nutrient.csv")
    nat = {c: i for i, c in enumerate(next(rows))}
    fdc_i, nid_i, amount_i = nat["fdc_id"], nat["nutrient_id"], nat["amount"]
    for row in rows:
        if (
            row[nid_i] in ids
            and row[fdc_i] in by_fdc
            and (value := to_number(row[amount_i])) is not None
        ):
            nutrients.setdefault(row[fdc_i], {})[int(row[nid_i])] = value

    fill: dict[str, UsdaFood] = {}
    for gtin, (_, fdc, row) in best.items():
        fill[gtin] = UsdaFood(
            description=descriptions.get(str(fdc)) or None,
            brand=row[at["brand_name"]] or row[at["brand_owner"]] or None,
            ingredients=row[at["ingredients"]] or None,
            category=row[at["branded_food_category"]] or None,
            nutrients=nutrients.get(str(fdc), {}),
        )
    return fill


def save_fill(fill: dict[str, UsdaFood], path: Path = FILL_CACHE) -> None:
    data = {g: {**f.__dict__, "nutrients": {str(k): v for k, v in f.nutrients.items()}}
            for g, f in fill.items()}  # fmt: skip
    with gzip.open(path, "wt", encoding="utf-8") as out:
        json.dump(data, out)


def load_fill(path: Path = FILL_CACHE) -> dict[str, UsdaFood]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    return {g: UsdaFood(**{**d, "nutrients": {int(k): v for k, v in d["nutrients"].items()}})
            for g, d in data.items()}  # fmt: skip
