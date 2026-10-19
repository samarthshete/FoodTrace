"""USDA FoodData Central live fallback (specs/012, USDA-7..10).

Only called when Open Food Facts doesn't have a barcode. Any USDA failure counts as "not
found" for that request, so a USDA outage never turns a 404 into a 503 (USDA-9).
"""

import logging
from typing import Any

import httpx

from app.services.gtin import InvalidGTIN, normalize
from app.services.usda_mapping import UsdaFood, category_map, to_number

log = logging.getLogger(__name__)
SEARCH_PATH = "/fdc/v1/foods/search"


def _matches(gtin: str, food: dict[str, Any]) -> bool:
    try:
        return normalize(str(food.get("gtinUpc") or "").lstrip("0").zfill(12)) == gtin
    except InvalidGTIN:
        return False


def to_food(food: dict[str, Any]) -> UsdaFood:
    nutrients: dict[int, float] = {}
    for n in food.get("foodNutrients") or []:
        if (value := to_number(n.get("value"))) is not None and n.get("nutrientId") is not None:
            nutrients[int(n["nutrientId"])] = value
    return UsdaFood(
        description=food.get("description") or None,
        brand=food.get("brandName") or food.get("brandOwner") or None,
        ingredients=food.get("ingredients") or None,
        category=food.get("brandedFoodCategory") or None,
        nutrients=nutrients,
    )


class USDAClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str, api_key: str, user_agent: str,
                 timeout_s: float = 4.0) -> None:  # fmt: skip
        self._http = http
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._headers = {"User-Agent": user_agent}
        self._timeout = timeout_s

    async def fetch(self, gtin: str) -> UsdaFood | None:
        """The newest Branded record for this GTIN, or None (USDA-7, USDA-9)."""
        params = {"query": gtin.zfill(14), "dataType": "Branded", "pageSize": "5",
                  "api_key": self._key}  # fmt: skip
        try:
            resp = await self._http.get(f"{self._base}{SEARCH_PATH}", params=params,
                                        headers=self._headers, timeout=self._timeout)  # fmt: skip
            resp.raise_for_status()
            foods = resp.json().get("foods") or []
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("USDA lookup failed for %s: %s", gtin, exc.__class__.__name__)
            return None
        hits = [f for f in foods if _matches(gtin, f)]
        if not hits:
            return None
        newest = max(hits, key=lambda f: (str(f.get("publishedDate") or ""), f.get("fdcId") or 0))
        food = to_food(newest)
        return None if category_map().is_excluded(food.category) else food  # USDA-3
