"""Products added from label photos (specs/017). The photo itself never reaches the server."""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.off_mapping import completeness

Kind = Literal["food", "drink", "cheese", "fat_oil_nut_seed"]
KIND_TAGS: dict[str, list[str]] = {  # CONTRIB-4: the tag that sets the Nutri-Score class
    "food": [],
    "drink": ["en:beverages"],
    "cheese": ["en:cheeses"],
    "fat_oil_nut_seed": ["en:fats"],
}
SOURCE = "contribution"


class NutritionIn(BaseModel):
    """Per 100 g, within physical limits (CONTRIB-4)."""

    model_config = ConfigDict(extra="forbid")
    energy_kj: float = Field(ge=0, le=3800)
    sugars_g: float = Field(ge=0, le=100)
    saturated_fat_g: float = Field(ge=0, le=100)
    salt_g: float = Field(ge=0, le=100)
    fat_g: float | None = Field(default=None, ge=0, le=100)
    fiber_g: float | None = Field(default=None, ge=0, le=100)
    proteins_g: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def saturated_within_fat(self) -> "NutritionIn":
        if self.fat_g is not None and self.saturated_fat_g > self.fat_g:
            raise ValueError("saturated_fat_g can't be more than fat_g")
        return self


class ContributionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gtin: str
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=200)
    ingredients_text: str | None = Field(default=None, max_length=5000)
    kind: Kind
    nutrition: NutritionIn
    share_with_off: bool = False


def product_row(gtin: str, c: ContributionIn, now: datetime) -> dict[str, Any]:
    """A `products` row from confirmed fields; every field's source is the contribution."""
    nutrition = {k: {"value": v, "estimated": False}
                 for k, v in c.nutrition.model_dump().items() if v is not None}  # fmt: skip
    categories = KIND_TAGS[c.kind]
    row: dict[str, Any] = {
        "gtin": gtin, "name": c.name.strip(), "brand": (c.brand or "").strip() or None,
        "primary_category": categories[-1] if categories else None, "categories": categories,
        "image_url": None, "ingredients_text": (c.ingredients_text or "").strip() or None,
        "nutrition": nutrition, "nova_group": None, "labels": [], "is_organic": False,
        "allergens": [], "traces": [], "ingredients_analysis": [],
        "additives_known": False, "fetched_at": now,
    }  # fmt: skip
    present = [
        k for k, v in row.items() if v not in (None, [], {}) and k not in ("gtin", "fetched_at")
    ]
    row["source_by_field"] = {k: SOURCE for k in present}
    row["completeness"] = completeness(nutrition, None, False)
    return row


def off_fields(gtin: str, c: ContributionIn) -> dict[str, str]:
    """Fields for Open Food Facts' product write API (CONTRIB-10)."""
    n = c.nutrition
    fields = {"code": gtin, "product_name": c.name, "countries": "United States",
              "nutrition_data_per": "100g", "nutriment_energy-kj": str(n.energy_kj),
              "nutriment_energy-kj_unit": "kJ", "nutriment_sugars": str(n.sugars_g),
              "nutriment_saturated-fat": str(n.saturated_fat_g),
              "nutriment_salt": str(n.salt_g)}  # fmt: skip
    optional = {"brands": c.brand, "ingredients_text_en": c.ingredients_text,
                "nutriment_fat": n.fat_g, "nutriment_fiber": n.fiber_g,
                "nutriment_proteins": n.proteins_g}  # fmt: skip
    fields.update({k: str(v) for k, v in optional.items() if v not in (None, "")})
    return fields


class RateLimiter:
    """At most `limit` events per key per hour, in memory (CONTRIB-8). Keys aren't persisted."""

    def __init__(self, limit: int, window_s: float = 3600, clock: Any = time.monotonic) -> None:
        self.limit, self.window, self.clock = limit, window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        events = self._events[key]
        while events and now - events[0] >= self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True
