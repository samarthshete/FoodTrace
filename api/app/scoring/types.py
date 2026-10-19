"""Value types for the scoring engine. Pure data, no I/O."""

from dataclasses import dataclass, field
from typing import Any, Literal

NutriClass = Literal["water", "beverage", "cheese", "fats_oils_nuts_seeds", "general"]
Component = Literal["nutrition", "additives", "processing"]

NUTRIENT_FIELDS = (
    "energy_kj",
    "sugars_g",
    "saturated_fat_g",
    "fat_g",
    "salt_g",
    "fiber_g",
    "proteins_g",
    "fvl_percent",
)


@dataclass(frozen=True)
class Nutrient:
    value: float
    estimated: bool = False


@dataclass(frozen=True)
class AdditiveInfo:
    code: str  # lower-case E-number without prefix, e.g. "e250"
    name: str
    risk_level: int | None = None  # 0-3, None = unrated
    evidence_grade: str | None = None  # "A" | "B" | "C"
    source_url: str | None = None


@dataclass(frozen=True)
class ProductFacts:
    """Everything the engine needs about one product, per 100 g/ml."""

    nutrients: dict[str, Nutrient] = field(default_factory=dict)
    category_tags: tuple[str, ...] = ()
    nova_group: int | None = None
    additives: tuple[AdditiveInfo, ...] | None = None  # None = additive list unknown
    ingredients_text: str | None = None  # EST-6: for estimating missing inputs

    def get(self, name: str) -> Nutrient | None:
        return self.nutrients.get(name)


@dataclass(frozen=True)
class BreakdownLine:
    rule_id: str
    component: Component
    points: float
    input_value: Any
    source_url: str
    estimated: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "rule_id": self.rule_id,
            "component": self.component,
            "points": self.points,
            "input_value": self.input_value,
            "source_url": self.source_url,
            "estimated": self.estimated,
        }
        if self.note is not None:
            out["note"] = self.note
        return out
