"""Map USDA FoodData Central Branded Foods data to our rows (specs/012).

Shared by the bulk gap-fill (pipeline/usda_bulk.py) and the live fallback (usda_client.py).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.services.off_mapping import KCAL_TO_KJ, completeness

CATEGORIES_PATH = Path(__file__).resolve().parents[3] / "config" / "usda_categories.yaml"
# USDA-1: nutrient ids (nutrient.csv) for the fields we score.
ENERGY_KJ, ENERGY_KCAL, SUGARS, SAT_FAT, FAT, SODIUM_MG, FIBER, PROTEIN = (
    1062, 1008, 2000, 1258, 1004, 1093, 1079, 1003,
)  # fmt: skip
NUTRIENT_IDS = frozenset({ENERGY_KJ, ENERGY_KCAL, SUGARS, SAT_FAT, FAT, SODIUM_MG, FIBER, PROTEIN})
_SEPARATORS = re.compile(r"[\s\-\u2013\u2014]+")  # spaces, hyphen, en and em dashes


@dataclass(frozen=True)
class UsdaFood:
    description: str | None
    brand: str | None
    ingredients: str | None
    category: str | None
    nutrients: dict[int, float] = field(default_factory=dict)  # per 100 g, by nutrient id


def category_key(name: str) -> str:
    """USDA spells one category several ways ('A  B', 'A - B', 'A \u2013 B'); key them alike."""
    return _SEPARATORS.sub(" ", name).strip().lower()


@dataclass(frozen=True)
class CategoryMap:
    tags: dict[str, list[str]]
    exclude: frozenset[str]

    def is_excluded(self, category: str | None) -> bool:  # USDA-3
        return category is not None and category_key(category) in self.exclude

    def categories(self, category: str | None) -> list[str]:  # USDA-2
        if not category:
            return []
        slug = "usda:" + "-".join(re.findall(r"[a-z0-9]+", category.lower()))
        return [*self.tags.get(category_key(category), []), slug]


@lru_cache(maxsize=1)
def category_map(path: Path = CATEGORIES_PATH) -> CategoryMap:
    raw = yaml.safe_load(path.read_text())
    return CategoryMap(
        tags={category_key(k): list(v) for k, v in raw["tags"].items()},
        exclude=frozenset(category_key(c) for c in raw["exclude"]),
    )


def to_number(raw: Any) -> float | None:
    """A non-negative amount, or None (USDA-1)."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def map_nutrition(nutrients: dict[int, float]) -> dict[str, dict[str, Any]]:
    """Our per-100 g nutrition dict from USDA nutrient amounts (USDA-1)."""
    energy = nutrients.get(ENERGY_KJ)
    if energy is None and (kcal := nutrients.get(ENERGY_KCAL)) is not None:
        energy = kcal * KCAL_TO_KJ
    sodium = nutrients.get(SODIUM_MG)
    values = {
        "energy_kj": energy,
        "sugars_g": nutrients.get(SUGARS),
        "saturated_fat_g": nutrients.get(SAT_FAT),
        "fat_g": nutrients.get(FAT),
        "salt_g": None if sodium is None else sodium / 1000 * 2.5,
        "fiber_g": nutrients.get(FIBER),
        "proteins_g": nutrients.get(PROTEIN),
    }
    return {
        k: {"value": round(v, 4), "estimated": False} for k, v in values.items() if v is not None
    }


def map_product(gtin: str, food: UsdaFood, fetched_at: datetime) -> dict[str, Any]:
    """A `products` row for a USDA-only product (USDA-8)."""
    categories = category_map().categories(food.category)
    nutrition = map_nutrition(food.nutrients)
    row: dict[str, Any] = {
        "gtin": gtin,
        "name": food.description,
        "brand": food.brand,
        "primary_category": categories[-1] if categories else None,
        "categories": categories,
        "image_url": None,
        "ingredients_text": food.ingredients,
        "nutrition": nutrition,
        "nova_group": None,
        "labels": [],
        "is_organic": False,
        "allergens": [],
        "traces": [],
        "ingredients_analysis": [],  # unknown for USDA (ACC-6)
        "additives_known": False,  # USDA has no parsed additive list (spec 014 derives it)
        "fetched_at": fetched_at,
    }
    present = [
        k for k, v in row.items() if v not in (None, [], {}) and k not in ("gtin", "fetched_at")
    ]
    row["source_by_field"] = {k: "usda" for k in present}
    row["completeness"] = completeness(nutrition, None, False)
    return row


def fill_gaps(row: dict[str, Any], food: UsdaFood) -> int:
    """Fill nutrients and ingredients an OFF row lacks, in place. Returns fields filled (USDA-5)."""
    filled = 0
    for key, value in map_nutrition(food.nutrients).items():
        if key not in row["nutrition"]:
            row["nutrition"][key] = value
            row["source_by_field"][f"nutrition.{key}"] = "usda"
            filled += 1
    if not row["ingredients_text"] and food.ingredients:
        row["ingredients_text"] = food.ingredients
        row["source_by_field"]["ingredients_text"] = "usda"
        filled += 1
    if filled:
        row["completeness"] = completeness(
            row["nutrition"], row["nova_group"], row["additives_known"]
        )
    return filled
