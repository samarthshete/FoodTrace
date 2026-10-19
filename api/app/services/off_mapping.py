"""Map an Open Food Facts product to our `products` row (specs/006, LOOKUP-13)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

KCAL_TO_KJ = 4.184
SODIUM_TO_SALT = 2.5
SCORING_INPUTS = ("energy_kj", "sugars_g", "saturated_fat_g", "salt_g", "fiber_g",
                  "proteins_g", "fvl_percent")  # fmt: skip


def _num(nutriments: dict[str, Any], key: str) -> float | None:
    raw = nutriments.get(key)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _nutrient(value: float | None, estimated: bool = False) -> dict[str, Any] | None:
    return None if value is None else {"value": round(value, 4), "estimated": estimated}


def map_nutrition(n: dict[str, Any]) -> dict[str, dict[str, Any]]:
    energy = _num(n, "energy-kj_100g")
    if energy is None and (kcal := _num(n, "energy-kcal_100g")) is not None:
        energy = kcal * KCAL_TO_KJ
    if energy is None:
        energy = _num(n, "energy_100g")
    salt = _num(n, "salt_100g")
    if salt is None and (sodium := _num(n, "sodium_100g")) is not None:
        salt = sodium * SODIUM_TO_SALT
    fvl = _num(n, "fruits-vegetables-legumes_100g")
    fvl_estimated = False
    if fvl is None:
        fvl = _num(n, "fruits-vegetables-legumes-estimate-from-ingredients_100g")
        fvl_estimated = fvl is not None
    mapped = {
        "energy_kj": _nutrient(energy),
        "sugars_g": _nutrient(_num(n, "sugars_100g")),
        "saturated_fat_g": _nutrient(_num(n, "saturated-fat_100g")),
        "fat_g": _nutrient(_num(n, "fat_100g")),
        "salt_g": _nutrient(salt),
        "fiber_g": _nutrient(_num(n, "fiber_100g")),
        "proteins_g": _nutrient(_num(n, "proteins_100g")),
        "fvl_percent": _nutrient(fvl, fvl_estimated),
    }
    return {k: v for k, v in mapped.items() if v is not None}


def _text(p: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = p.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _tags(p: dict[str, Any], key: str) -> list[str]:
    value = p.get(key)
    return [t for t in value if isinstance(t, str)] if isinstance(value, list) else []


def additive_codes(p: dict[str, Any]) -> list[str] | None:
    """`en:e322i` -> `e322i`. None when the additive list is unknown (ADD-6)."""
    tags = p.get("additives_tags")
    if not isinstance(tags, list) and _text(p, "ingredients_text", "ingredients_text_en") is None:
        return None
    return sorted({t.split(":", 1)[-1] for t in _tags(p, "additives_tags")})


def map_product(gtin: str, p: dict[str, Any], fetched_at: datetime) -> dict[str, Any]:
    nutrition = map_nutrition(p.get("nutriments") or {})
    nova = p.get("nova_group")
    nova = nova if isinstance(nova, int) and 1 <= nova <= 4 else None
    categories = _tags(p, "categories_tags")
    labels = _tags(p, "labels_tags")
    codes = additive_codes(p)
    row: dict[str, Any] = {
        "gtin": gtin,
        "name": _text(p, "product_name_en", "product_name"),
        "brand": (_text(p, "brands") or "").split(",")[0].strip() or None,
        "primary_category": categories[-1] if categories else None,  # most specific
        "categories": categories,
        "image_url": _text(p, "image_front_url"),
        "ingredients_text": _text(p, "ingredients_text_en", "ingredients_text"),
        "nutrition": nutrition,
        "nova_group": nova,
        "labels": labels,
        "is_organic": "en:organic" in labels,
        "allergens": _tags(p, "allergens_tags"),  # ACC-6
        "traces": _tags(p, "traces_tags"),
        "ingredients_analysis": _tags(p, "ingredients_analysis_tags"),
        "additives_known": codes is not None,
        "fetched_at": fetched_at,
    }
    present = [k for k, v in row.items() if v not in (None, [], {}) and k != "fetched_at"]
    row["source_by_field"] = {k: "off" for k in present if k != "gtin"}
    row["completeness"] = completeness(nutrition, nova, codes is not None)
    return row


def completeness(nutrition: dict[str, Any], nova: int | None, additives_known: bool) -> Decimal:
    """Share of scoring inputs present: the nutrients, NOVA and the additive list."""
    present = sum(1 for k in SCORING_INPUTS if k in nutrition) + (nova is not None)
    present += additives_known
    return Decimal(present / (len(SCORING_INPUTS) + 2)).quantize(Decimal("0.01"))
