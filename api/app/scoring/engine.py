"""Combine N, A and P into a 0-100 score with a full breakdown (specs/005-engine.md).

Pure and deterministic: no I/O, no clock, no randomness (ENGINE-4).
"""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from app.scoring import additives, ingredients, nutriscore_2023, processing
from app.scoring.config import ScoringConfig, default_config
from app.scoring.types import BreakdownLine, Component, Nutrient, ProductFacts

CONFIDENCE_INPUTS = ("energy_kj", "sugars_g", "saturated_fat_g", "salt_g",
                     "fiber_g", "proteins_g", "fvl_percent")  # fmt: skip


@dataclass(frozen=True)
class ScoreResult:
    engine_version: str
    status: str  # "scored" | "not_scored"
    total: int | None
    band: dict[str, str] | None
    confidence: float
    missing_inputs: tuple[str, ...]
    nutriscore: dict[str, Any]
    components: dict[str, dict[str, Any]]
    breakdown: tuple[BreakdownLine, ...]

    def to_dict(self, *, with_breakdown: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "engine_version": self.engine_version,
            "status": self.status,
            "total": self.total,
            "band": self.band,
            "confidence": self.confidence,
            "missing_inputs": list(self.missing_inputs),
            "nutriscore": self.nutriscore,
            "components": self.components,
        }
        if with_breakdown:
            out["breakdown"] = [line.to_dict() for line in self.breakdown]
        return out


def round_half_up(x: float, places: int = 0) -> Decimal:
    quantum = Decimal(1).scaleb(-places)
    return Decimal(repr(x)).quantize(quantum, rounding=ROUND_HALF_UP)


def band_for(total: int, cfg: ScoringConfig) -> dict[str, str]:
    for band in cfg.bands:  # ordered from the top
        if total >= band.min:
            return {"id": band.id, "label": band.label}
    raise ValueError(f"no band for total {total}")


def _confidence(facts: ProductFacts) -> float:
    """ENGINE-10: share of inputs present and not estimated."""
    present = sum(
        1 for name in CONFIDENCE_INPUTS
        if (n := facts.get(name)) is not None and not n.estimated
    )  # fmt: skip
    present += facts.nova_group is not None
    present += facts.additives is not None
    return float(round_half_up(present / (len(CONFIDENCE_INPUTS) + 2), 2))


def nutrition_value(ns_score: int, nutri_class: str, lo: int, hi: int, cfg: ScoringConfig) -> float:
    """N from the Nutri-Score, by grade (ENGINE-1).

    Grade boundaries map to `nutrition_anchors` (A 1.0-0.8 ... E 0.2-0); in between, N falls
    linearly, so it's continuous across boundaries. The class's best score gives 1.0, the
    worst 0.0.
    """
    bounds = nutriscore_2023.grade_bounds(nutri_class, cfg.nutriscore)  # type: ignore[arg-type]
    grades = [g for g in ("a", "b", "c", "d") if g in bounds]
    xs = [float(lo), *(bounds[g] + 0.5 for g in grades), float(hi)]
    ys = [1.0, *(cfg.nutrition_anchors[g] for g in grades), 0.0]
    s = min(max(float(ns_score), xs[0]), xs[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= s <= xs[i + 1]:
            t = 0.0 if xs[i + 1] == xs[i] else (s - xs[i]) / (xs[i + 1] - xs[i])
            return round(ys[i] + t * (ys[i + 1] - ys[i]), 4)
    return 0.0


def _with_estimates(
    facts: ProductFacts, cfg: ScoringConfig
) -> tuple[ProductFacts, ingredients.NovaEstimate | None]:
    """Fill inputs the label data lacks from the ingredient list (specs/014)."""
    parsed = ingredients.split_ingredients(facts.ingredients_text)  # EST-1
    if facts.get("fvl_percent") is None:
        fvl = ingredients.estimate_fvl(parsed, cfg.estimates)  # EST-2
        if fvl is not None:
            nutrients = {**facts.nutrients, "fvl_percent": Nutrient(fvl, estimated=True)}
            facts = replace(facts, nutrients=nutrients)
    nova = (
        None if facts.nova_group is not None else ingredients.estimate_nova(parsed, cfg.estimates)
    )
    return facts, nova


def score(facts: ProductFacts, cfg: ScoringConfig | None = None) -> ScoreResult:
    cfg = cfg or default_config()
    facts, nova_estimate = _with_estimates(facts, cfg)
    codes = [a.code for a in facts.additives or ()]
    ns = nutriscore_2023.compute(facts, cfg.nutriscore, codes)
    add = additives.compute(facts.additives, cfg.additives)
    proc = processing.compute(facts.nova_group, cfg.processing, nova_estimate)

    n_value: float | None = None
    if ns.nutri_class == "water":
        n_value = 1.0  # ENGINE-1
    elif ns.computable and ns.score is not None and ns.min_score is not None:
        assert ns.max_score is not None
        n_value = nutrition_value(ns.score, ns.nutri_class, ns.min_score, ns.max_score, cfg)

    values = {"nutrition": n_value, "additives": add.value, "processing": proc.value}
    missing = list(ns.missing)
    if not add.known:
        missing.append("additives")
    if not proc.known:
        missing.append("nova_group")

    components = {
        name: {"weight": cfg.weights[name], "value": v, "known": v is not None}
        for name, v in values.items()
    }
    breakdown = [*ns.lines, *add.lines, *proc.lines]
    nutri = {"class": ns.nutri_class, "score": ns.score, "grade": ns.grade}

    def result(status: str, total: int | None) -> ScoreResult:
        return ScoreResult(
            engine_version=cfg.engine_version,
            status=status,
            total=total,
            band=band_for(total, cfg) if total is not None else None,
            confidence=_confidence(facts),
            missing_inputs=tuple(missing),
            nutriscore=nutri,
            components=components,
            breakdown=tuple(breakdown),
        )

    if n_value is None:  # ENGINE-3: not scored
        return result("not_scored", None)

    known = {k: v for k, v in values.items() if v is not None}  # ENGINE-5
    known_weight = sum(cfg.weights[k] for k in known)
    for name, value in known.items():  # ENGINE-9
        share = cfg.weights[name] * value / known_weight * 100
        breakdown.append(BreakdownLine(
            f"component.{name}", cast(Component, name), float(round_half_up(share, 2)),
            value, f"/methodology#{name}",
        ))  # fmt: skip
    raw = sum(cfg.weights[k] * v for k, v in known.items()) / known_weight * 100
    total = int(round_half_up(raw))  # ENGINE-2

    if add.cap_applies:  # ENGINE-6
        capped = min(total, cfg.additives.cap_total)
        breakdown.append(BreakdownLine(
            "additives.cap", "additives", capped - total, cfg.additives.cap_total,
            cfg.additives.efsa_source,
            note="An additive with a high EFSA overexposure risk caps the score.",
        ))  # fmt: skip
        total = capped

    cap = cfg.nutriscore_cap  # ENGINE-14: poor nutrition caps the total
    if ns.grade in cap.grades and total > cap.total:
        breakdown.append(BreakdownLine(
            "nutrition.cap", "nutrition", cap.total - total, cap.total,
            cfg.nutriscore.source_urls["foods"],
            note=f"A Nutri-Score of {ns.grade.upper()} caps the score at {cap.total}.",
        ))  # fmt: skip
        total = cap.total

    return result("scored", total)
