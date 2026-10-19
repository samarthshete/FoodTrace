from typing import Any

import pytest

from app.scoring import nutriscore_2023 as ns
from app.scoring.config import default_config

from .factories import SNACK, additive, facts

spec = pytest.mark.spec
CFG = default_config().nutriscore


def compute(**kw: object) -> ns.NutriScoreResult:
    f = facts(**kw)  # type: ignore[arg-type]
    return ns.compute(f, CFG, [a.code for a in f.additives or ()])


def pts(result: ns.NutriScoreResult, component: str) -> float:
    [line] = [ln for ln in result.lines if ln.rule_id.endswith("." + component)]
    return line.points


# --- Class (NS-1, NS-2) ---


@spec("NS-1")
@pytest.mark.parametrize(
    ("tags", "codes", "expected"),
    [
        (("en:mineral-waters",), [], "water"),
        (("en:waters", "en:flavored-waters"), [], "beverage"),
        (("en:waters",), ["e951"], "beverage"),
        (("en:beverages", "en:cheeses"), [], "beverage"),
        (("en:beverages", "en:alcoholic-beverages"), [], "general"),
        (("en:milks",), [], "beverage"),
        (("en:cheeses",), [], "cheese"),
        (("en:olive-oils",), [], "fats_oils_nuts_seeds"),
        (("en:nuts", "en:chestnuts"), [], "general"),
        (("en:breakfast-cereals",), [], "general"),
        ((), [], "general"),
    ],
)
def test_classify(tags: tuple[str, ...], codes: list[str], expected: str) -> None:
    assert ns.classify(tags, codes, CFG)[0] == expected


@spec("NS-2")
def test_red_meat_flag() -> None:
    assert ns.classify(("en:meats", "en:beef"), [], CFG)[1] is True
    assert ns.classify(("en:meats", "en:chicken"), [], CFG)[1] is False


# --- Required inputs (NS-3, NS-4) ---


@spec("NS-3")
@pytest.mark.parametrize("drop", ["energy_kj", "sugars_g", "saturated_fat_g", "salt_g"])
def test_missing_required_nutrient_is_not_computable(drop: str) -> None:
    values = {k: v for k, v in SNACK.items() if k != drop}
    r = compute(**values)
    assert not r.computable and r.score is None and r.grade is None
    assert drop in r.missing


@spec("NS-3")
def test_fats_class_also_requires_total_fat() -> None:
    r = compute(tags=("en:olive-oils",), energy_kj=3700, sugars_g=0, saturated_fat_g=14, salt_g=0)
    assert not r.computable and "fat_g" in r.missing


@spec("NS-4")
def test_missing_optional_scores_zero_and_is_reported() -> None:
    values = {k: v for k, v in SNACK.items() if k not in ("fiber_g", "fvl_percent")}
    r = compute(**values)
    assert r.computable
    assert r.score == 13  # A = 13, nothing favourable
    assert set(r.missing) == {"fiber_g", "fvl_percent"}


# --- Unfavourable points (NS-5..NS-8) ---


@spec("NS-5", "NS-12")
def test_general_worked_example() -> None:
    r = compute(**SNACK)
    assert [pts(r, c) for c in ("energy", "sugars", "saturated_fat", "salt")] == [4, 3, 2, 4]
    assert pts(r, "proteins") == 0  # A >= 11: protein not counted
    assert pts(r, "fiber") == -2
    assert (r.score, r.grade) == (11, "d")


@spec("NS-5")
def test_general_maxima() -> None:
    r = compute(energy_kj=4000, sugars_g=60, saturated_fat_g=20, salt_g=5,
                fiber_g=0, proteins_g=0, fvl_percent=0)  # fmt: skip
    assert r.score == 55


@spec("NS-6")
def test_fats_olive_oil_is_b() -> None:
    # EFS = 14 * 37 = 518 kJ -> 4; ratio 14% -> 1; A = 5 < 7; fvl 100% -> 5 => 0, grade B
    r = compute(tags=("en:olive-oils",), energy_kj=3700, fat_g=100, saturated_fat_g=14,
                sugars_g=0, salt_g=0, fiber_g=0, proteins_g=0, fvl_percent=100)  # fmt: skip
    assert pts(r, "energy_from_saturates") == 4
    assert pts(r, "saturates_ratio") == 1
    assert (r.score, r.grade) == (0, "b")


@spec("NS-6")
def test_fats_zero_fat_ratio_is_zero() -> None:
    r = compute(tags=("en:fats",), energy_kj=100, fat_g=0, saturated_fat_g=0,
                sugars_g=0, salt_g=0)  # fmt: skip
    assert pts(r, "saturates_ratio") == 0


@spec("NS-7")
def test_beverage_cola() -> None:
    # energy 180 -> 3, sugars 10.6 -> 9 => A = 12, grade E
    r = compute(tags=("en:sodas", "en:beverages"), energy_kj=180, sugars_g=10.6,
                saturated_fat_g=0, salt_g=0.01, fiber_g=0, proteins_g=0, fvl_percent=0)  # fmt: skip
    assert (pts(r, "energy"), pts(r, "sugars")) == (3, 9)
    assert (r.score, r.grade) == (12, "e")


@spec("NS-7")
def test_beverage_sweeteners_add_four_points() -> None:
    r = compute(tags=("en:beverages",), additives=(additive("e951"),), energy_kj=1.5,
                sugars_g=0, saturated_fat_g=0, salt_g=0.02, fiber_g=0, proteins_g=0,
                fvl_percent=0)  # fmt: skip
    assert pts(r, "sweeteners") == 4
    assert (r.score, r.grade) == (4, "c")


@spec("NS-8")
@pytest.mark.parametrize(("value", "expected"), [(3.4, 0), (3.41, 1), (51, 14), (51.01, 15)])
def test_threshold_is_strictly_greater(value: float, expected: int) -> None:
    assert ns.points_above(value, CFG.general.sugars_g) == expected


@spec("NS-8")
@pytest.mark.parametrize(("ratio", "expected"), [(9.99, 0), (10, 1), (63.99, 9), (64, 10)])
def test_saturates_ratio_uses_greater_or_equal(ratio: float, expected: int) -> None:
    assert (
        ns.points_at_or_above(ratio, CFG.fats_oils_nuts_seeds.saturates_ratio_percent) == expected
    )


# --- Favourable points (NS-9..NS-11) ---


@spec("NS-9")
@pytest.mark.parametrize(("fvl", "expected"), [(40, 0), (40.1, 1), (60.1, 2), (80, 2), (80.1, 5)])
def test_general_fvl_points(fvl: float, expected: int) -> None:
    assert ns.fvl_points(fvl, CFG.general.fvl_percent) == expected


@spec("NS-9")
@pytest.mark.parametrize(("protein", "expected"), [(2.4, 0), (2.5, 1), (17, 6), (17.1, 7)])
def test_general_protein_points(protein: float, expected: int) -> None:
    assert ns.points_above(protein, CFG.general.proteins_g) == expected


@spec("NS-10")
def test_beverage_orange_juice() -> None:
    # energy 190 -> 3, sugars 9 -> 7 => A = 10; fvl 100% -> 6 => 4, grade C
    r = compute(tags=("en:fruit-juices", "en:beverages"), energy_kj=190, sugars_g=9,
                saturated_fat_g=0, salt_g=0, fiber_g=0.2, proteins_g=0.7,
                fvl_percent=100)  # fmt: skip
    assert pts(r, "fvl") == -6
    assert (r.score, r.grade) == (4, "c")


@spec("NS-10")
@pytest.mark.parametrize(("protein", "expected"), [(1.2, 0), (1.21, 1), (3.0, 6), (3.3, 7)])
def test_beverage_protein_points(protein: float, expected: int) -> None:
    assert ns.points_above(protein, CFG.beverage.proteins_g) == expected


@spec("NS-11")
def test_red_meat_protein_capped_at_two() -> None:
    # energy 800 -> 2, sat 3 -> 2 => A = 4; protein 20 -> 7, capped to 2 => score 2
    beef = dict(energy_kj=800, sugars_g=0, saturated_fat_g=3, salt_g=0.1,
                fiber_g=0, proteins_g=20, fvl_percent=0)  # fmt: skip
    capped = compute(tags=("en:beef",), **beef)
    assert pts(capped, "proteins") == -2
    assert (capped.score, capped.grade) == (2, "b")
    assert compute(tags=("en:chicken",), **beef).score == -3


# --- Final score (NS-12..NS-16) ---


@spec("NS-12")
def test_general_protein_counted_below_cutoff() -> None:
    r = compute(**{**SNACK, "salt_g": 0.3})  # salt -> 1, A = 10 < 11
    assert pts(r, "proteins") == -3
    assert r.score == 10 - 3 - 2


@spec("NS-13")
def test_cheese_always_counts_protein() -> None:
    r = compute(tags=("en:cheeses",), **SNACK)  # A = 13, protein 8 -> 3
    assert pts(r, "proteins") == -3
    assert (r.score, r.grade) == (8, "c")


@spec("NS-14")
def test_fats_protein_not_counted_at_seven_or_more() -> None:
    # Butter: EFS 1887 -> 10, ratio 62.2% -> 9 => A = 19, grade E
    r = compute(tags=("en:butters",), energy_kj=3000, fat_g=82, saturated_fat_g=51,
                sugars_g=0.6, salt_g=0.02, proteins_g=5, fiber_g=0, fvl_percent=0)  # fmt: skip
    assert pts(r, "proteins") == 0
    assert (r.score, r.grade) == (19, "e")


@spec("NS-15")
def test_beverage_protein_always_counted() -> None:
    r = compute(tags=("en:beverages",), energy_kj=400, sugars_g=12, saturated_fat_g=0,
                salt_g=0, fiber_g=0, proteins_g=3.3, fvl_percent=0)  # fmt: skip
    assert pts(r, "proteins") == -7
    assert r.score == 20 - 7


@spec("NS-16")
def test_water_is_grade_a_without_nutrients() -> None:
    r = compute(tags=("en:spring-waters",))
    assert r.computable and r.grade == "a" and r.score is None


# --- Grades (NS-17..NS-19) ---


@spec("NS-17")
@pytest.mark.parametrize(
    ("score", "grade"),
    [(-5, "a"), (0, "a"), (1, "b"), (2, "b"), (3, "c"), (10, "c"), (11, "d"), (18, "d"),
     (19, "e")],
)  # fmt: skip
def test_general_grades(score: int, grade: str) -> None:
    assert ns.grade_for(score, "general", CFG) == grade
    assert ns.grade_for(score, "cheese", CFG) == grade


@spec("NS-18")
@pytest.mark.parametrize(
    ("score", "grade"), [(-6, "a"), (-5, "b"), (2, "b"), (3, "c"), (18, "d"), (19, "e")]
)
def test_fats_grades(score: int, grade: str) -> None:
    assert ns.grade_for(score, "fats_oils_nuts_seeds", CFG) == grade


@spec("NS-19")
@pytest.mark.parametrize(
    ("score", "grade"),
    [(-10, "b"), (2, "b"), (3, "c"), (6, "c"), (7, "d"), (9, "d"), (10, "e")],
)
def test_beverage_grades_never_a(score: int, grade: str) -> None:
    assert ns.grade_for(score, "beverage", CFG) == grade


# --- Output (NS-20, NS-21) ---


@spec("NS-20")
def test_lines_carry_rule_ids_values_and_sources() -> None:
    r = compute(**SNACK)
    ids = [ln.rule_id for ln in r.lines]
    components = ("energy", "sugars", "saturated_fat", "salt", "proteins", "fiber", "fvl")
    assert ids == [f"nutriscore.general.{c}" for c in components]
    assert all(ln.source_url.startswith("https://") for ln in r.lines)
    assert next(ln for ln in r.lines if ln.rule_id.endswith("sugars")).input_value == 12


@spec("NS-20")
def test_estimated_flag_is_carried() -> None:
    r = compute(estimated=("fvl_percent",), **SNACK)
    fvl = next(ln for ln in r.lines if ln.rule_id.endswith(".fvl"))
    assert fvl.estimated


@spec("NS-21")
def test_score_ranges() -> None:
    assert ns.score_range("general", CFG) == (-17, 55)
    assert ns.score_range("fats_oils_nuts_seeds", CFG) == (-17, 55)
    assert ns.score_range("beverage", CFG) == (-18, 54)
    r = compute(**SNACK)
    assert (r.min_score, r.max_score) == (-17, 55)


@spec("NS-22")
def test_olive_rapeseed_and_walnut_oils_count_as_100_percent_fvl() -> None:
    cfg = default_config().nutriscore
    evoo: dict[str, Any] = dict(energy_kj=3622.0, sugars_g=0.0, saturated_fat_g=13.986,
                                fat_g=97.9, salt_g=0.0, fiber_g=0.0, proteins_g=0.0,
                                fvl_percent=0.0)  # fmt: skip
    olive = ns.compute(
        facts(tags=("en:fats", "en:vegetable-oils", "en:olive-oils"), **evoo), cfg, []
    )
    sunflower = ns.compute(facts(tags=("en:fats", "en:sunflower-oils"), **evoo), cfg, [])
    assert (olive.score, olive.grade) == (0, "b")  # matches Open Food Facts for EVOO
    assert sunflower.score == 5
    fvl = next(ln for ln in olive.lines if ln.rule_id.endswith(".fvl"))
    assert fvl.input_value == 100.0 and fvl.note and not fvl.estimated


@spec("NS-1")
def test_crisps_tagged_as_cheese_are_general_foods() -> None:
    tags = ("en:cheeses", "en:fermented-milk-products", "en:salty-snacks", "en:crisps")
    assert ns.classify(tags, [], CFG)[0] == "general"
    assert ns.classify(("en:cheeses",), [], CFG)[0] == "cheese"
