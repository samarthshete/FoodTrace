"""Nutri-Score 2023, ported from the Scientific Committee reports (specs/002).

Clean-room: written from the published point tables, not from Open Food Facts code.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.scoring.config import NutriScoreConfig
from app.scoring.types import BreakdownLine, NutriClass, ProductFacts

REQUIRED = ("energy_kj", "sugars_g", "saturated_fat_g", "salt_g")
OPTIONAL = ("fiber_g", "proteins_g", "fvl_percent")


@dataclass(frozen=True)
class NutriScoreResult:
    nutri_class: NutriClass
    computable: bool
    score: int | None
    grade: str | None
    min_score: int | None
    max_score: int | None
    missing: tuple[str, ...]
    lines: tuple[BreakdownLine, ...]


def points_above(value: float, thresholds: Sequence[float]) -> int:
    """Points = number of thresholds the value is strictly greater than (NS-8)."""
    return sum(1 for t in thresholds if value > t)


def points_at_or_above(value: float, lower_bounds: Sequence[float]) -> int:
    """Fats saturates ratio: bands use >= on each lower bound (NS-8)."""
    return sum(1 for t in lower_bounds if value >= t)


def fvl_points(value: float, table: Sequence[tuple[float, int]]) -> int:
    return max((pts for t, pts in table if value > t), default=0)


def classify(
    tags: Iterable[str], additive_codes: Iterable[str], cfg: NutriScoreConfig
) -> tuple[NutriClass, bool]:
    """Return (class, is_red_meat) from category tags (NS-1, NS-2)."""
    tagset = set(tags)
    c = cfg.classes
    has_nns = bool(set(additive_codes) & set(cfg.non_nutritive_sweeteners))
    is_red_meat = bool(tagset & set(cfg.red_meat_tags))

    def hit(include: list[str], exclude: list[str]) -> bool:
        return bool(tagset & set(include)) and not tagset & set(exclude)

    if hit(c.water, c.water_exclude) and not has_nns:
        return "water", is_red_meat
    if hit(c.beverage + c.water, c.beverage_exclude):  # flavoured/sweetened water is a beverage
        return "beverage", is_red_meat
    if hit(c.cheese, c.cheese_exclude):
        return "cheese", is_red_meat
    if hit(c.fats_oils_nuts_seeds, c.fats_oils_nuts_seeds_exclude):
        return "fats_oils_nuts_seeds", is_red_meat
    return "general", is_red_meat


def grade_bounds(nutri_class: NutriClass, cfg: NutriScoreConfig) -> dict[str, int]:
    """Upper score bound of each grade for the class (NS-17..NS-19)."""
    return {
        "general": cfg.general.grades,
        "cheese": cfg.general.grades,
        "fats_oils_nuts_seeds": cfg.fats_oils_nuts_seeds.grades,
        "beverage": cfg.beverage.grades,
        "water": {},
    }[nutri_class]


def grade_for(score: int, nutri_class: NutriClass, cfg: NutriScoreConfig) -> str:
    bounds = grade_bounds(nutri_class, cfg)
    for grade in ("a", "b", "c", "d"):
        if grade in bounds and score <= bounds[grade]:
            return grade
    return "e"


@dataclass(frozen=True)
class _Tables:
    """Point tables resolved for one class."""

    energy: tuple[str, Sequence[float]]  # (input name, thresholds)
    saturates_kind: str  # "grams" | "ratio"
    saturates: Sequence[float]
    sugars: Sequence[float]
    salt: Sequence[float]
    proteins: Sequence[float]
    fiber: Sequence[float]
    fvl: Sequence[tuple[float, int]]


def _tables(nutri_class: NutriClass, cfg: NutriScoreConfig) -> _Tables:
    g, f, b = cfg.general, cfg.fats_oils_nuts_seeds, cfg.beverage
    if nutri_class == "fats_oils_nuts_seeds":
        return _Tables(
            ("energy_from_saturates_kj", f.energy_from_saturates_kj),
            "ratio", f.saturates_ratio_percent,
            g.sugars_g, g.salt_g, g.proteins_g, g.fiber_g, g.fvl_percent,
        )  # fmt: skip
    if nutri_class == "beverage":
        return _Tables(
            ("energy_kj", b.energy_kj), "grams", g.saturated_fat_g,
            b.sugars_g, g.salt_g, b.proteins_g, g.fiber_g, b.fvl_percent,
        )  # fmt: skip
    return _Tables(
        ("energy_kj", g.energy_kj), "grams", g.saturated_fat_g,
        g.sugars_g, g.salt_g, g.proteins_g, g.fiber_g, g.fvl_percent,
    )  # fmt: skip


def max_points(nutri_class: NutriClass, cfg: NutriScoreConfig) -> dict[str, int]:
    """Most points each component can score in the class, keyed like the rule ids."""
    t = _tables(nutri_class, cfg)
    sat = "saturates_ratio" if t.saturates_kind == "ratio" else "saturated_fat"
    energy = "energy_from_saturates" if t.energy[0] == "energy_from_saturates_kj" else "energy"
    return {energy: len(t.energy[1]), sat: len(t.saturates), "sugars": len(t.sugars),
            "salt": len(t.salt), "proteins": len(t.proteins), "fiber": len(t.fiber),
            "fvl": max(pts for _, pts in t.fvl)}  # fmt: skip


def score_range(nutri_class: NutriClass, cfg: NutriScoreConfig) -> tuple[int, int]:
    """Theoretical (min, max) score for a class (NS-21)."""
    t = _tables(nutri_class, cfg)
    max_a = len(t.energy[1]) + len(t.saturates) + len(t.sugars) + len(t.salt)
    if nutri_class == "beverage":
        max_a += cfg.beverage.sweeteners_points
    max_c = len(t.proteins) + len(t.fiber) + max(pts for _, pts in t.fvl)
    return -max_c, max_a


def compute(
    facts: ProductFacts, cfg: NutriScoreConfig, additive_codes: Iterable[str] = ()
) -> NutriScoreResult:
    codes = list(additive_codes)
    nutri_class, is_red_meat = classify(facts.category_tags, codes, cfg)
    if nutri_class == "water":  # NS-16
        water = BreakdownLine(
            "nutriscore.water", "nutrition", 0, "water", cfg.source_urls["beverages"],
            note="Water is always grade A.",
        )  # fmt: skip
        return NutriScoreResult("water", True, None, "a", None, None, (), (water,))

    required = REQUIRED + (("fat_g",) if nutri_class == "fats_oils_nuts_seeds" else ())
    missing_required = tuple(n for n in required if facts.get(n) is None)
    missing_optional = tuple(n for n in OPTIONAL if facts.get(n) is None)
    if missing_required:  # NS-3
        return NutriScoreResult(
            nutri_class, False, None, None, None, None,
            missing_required + missing_optional, (),
        )  # fmt: skip

    t = _tables(nutri_class, cfg)
    source = cfg.source_urls["beverages" if nutri_class == "beverage" else "foods"]
    prefix = f"nutriscore.{nutri_class}"

    def val(name: str) -> float:
        n = facts.get(name)
        return n.value if n is not None else 0.0

    def est(name: str) -> bool:
        n = facts.get(name)
        return n.estimated if n is not None else False

    def line(
        component: str, pts: int, value: object, estimated: bool, note: str | None = None
    ) -> BreakdownLine:
        return BreakdownLine(
            f"{prefix}.{component}", "nutrition", pts, value, source, estimated, note
        )

    unfavourable: list[BreakdownLine] = []
    if t.energy[0] == "energy_from_saturates_kj":  # NS-6
        efs = round(val("saturated_fat_g") * cfg.fats_oils_nuts_seeds.kj_per_g_saturates, 2)
        unfavourable.append(
            line("energy_from_saturates", points_above(efs, t.energy[1]), efs,
                 est("saturated_fat_g"))
        )  # fmt: skip
    else:
        energy = val("energy_kj")
        unfavourable.append(
            line("energy", points_above(energy, t.energy[1]), energy, est("energy_kj"))
        )
    unfavourable.append(
        line("sugars", points_above(val("sugars_g"), t.sugars), val("sugars_g"), est("sugars_g"))
    )
    if t.saturates_kind == "ratio":
        fat = val("fat_g")
        ratio = round(val("saturated_fat_g") / fat * 100, 2) if fat > 0 else 0.0
        unfavourable.append(
            line("saturates_ratio", points_at_or_above(ratio, t.saturates), ratio,
                 est("saturated_fat_g") or est("fat_g"))
        )  # fmt: skip
    else:
        sat = val("saturated_fat_g")
        unfavourable.append(
            line("saturated_fat", points_above(sat, t.saturates), sat, est("saturated_fat_g"))
        )
    unfavourable.append(
        line("salt", points_above(val("salt_g"), t.salt), val("salt_g"), est("salt_g"))
    )
    if nutri_class == "beverage":  # NS-7
        has_nns = bool(set(codes) & set(cfg.non_nutritive_sweeteners))
        unfavourable.append(
            line("sweeteners", cfg.beverage.sweeteners_points if has_nns else 0, has_nns, False)
        )
    a_points = sum(int(ln.points) for ln in unfavourable)

    fiber_pts = points_above(val("fiber_g"), t.fiber)
    fvl_value, fvl_note = val("fvl_percent"), None
    if nutri_class == "fats_oils_nuts_seeds" and set(facts.category_tags) & set(cfg.fvl_oil_tags):
        fvl_value, fvl_note = 100.0, "Olive, rapeseed and walnut oils count as 100%."  # NS-22
    fvl_pts = fvl_points(fvl_value, t.fvl)
    protein_pts = points_above(val("proteins_g"), t.proteins)
    protein_note = None
    if nutri_class == "general" and is_red_meat:  # NS-11
        capped = min(protein_pts, cfg.general.red_meat_max_protein_points)
        if capped < protein_pts:
            protein_note = "Red meat: protein points capped."
        protein_pts = capped

    count_protein = True  # NS-12..NS-15
    if nutri_class == "general" and a_points >= cfg.general.protein_cutoff_a_points:
        count_protein = False
    if (
        nutri_class == "fats_oils_nuts_seeds"
        and a_points >= cfg.fats_oils_nuts_seeds.protein_cutoff_a_points
    ):
        count_protein = False
    if not count_protein:
        protein_note = "Not counted: unfavourable points are too high."
        protein_pts = 0

    # Favourable points carry a negative sign in the breakdown (they lower the score).
    favourable = [
        line("proteins", -protein_pts, val("proteins_g"), est("proteins_g"), protein_note),
        line("fiber", -fiber_pts, val("fiber_g"), est("fiber_g")),
        line("fvl", -fvl_pts, fvl_value, est("fvl_percent") and fvl_note is None, fvl_note),
    ]
    score = a_points - protein_pts - fiber_pts - fvl_pts
    lo, hi = score_range(nutri_class, cfg)
    return NutriScoreResult(
        nutri_class, True, score, grade_for(score, nutri_class, cfg), lo, hi,
        missing_optional, tuple(unfavourable + favourable),
    )  # fmt: skip
