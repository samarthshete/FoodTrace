import json
import random
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.scoring.config import default_config
from app.scoring.engine import band_for, score
from app.scoring.explain import explain
from app.scoring.types import AdditiveInfo, Nutrient, ProductFacts

from .factories import SNACK, additive, facts

spec = pytest.mark.spec
CFG = default_config()
BANNED = ("toxic", "dangerous", "unsafe")


@spec("ENGINE-1", "ENGINE-2", "ENGINE-14")
def test_worked_example_total() -> None:
    # Nutri-Score 11 is a D (11-18): N runs 0.4 -> 0.2 across 10.5..18.5, so 11 -> 0.3875.
    # 60 * 0.3875 + 30 * 1 (no additives) + 10 * 0 (NOVA 4) = 53.25 -> 53, then the D cap -> 49.
    r = score(facts(nova=4, **SNACK))
    assert r.components["nutrition"]["value"] == pytest.approx(0.3875)
    assert r.total == 49 and r.status == "scored"
    cap = next(ln for ln in r.breakdown if ln.rule_id == "nutrition.cap")
    assert cap.points == -4 and cap.note == "A Nutri-Score of D caps the score at 49."


@spec("ENGINE-1")
@pytest.mark.parametrize(
    ("ns_score", "n"),
    [(-17, 1.0), (0, 0.8057), (1, 0.75), (2, 0.65), (3, 0.5875), (10, 0.4125), (11, 0.3875),
     (18, 0.2125), (19, 0.1973), (55, 0.0), (99, 0.0)],
)  # fmt: skip
def test_nutrition_value_by_grade_is_continuous(ns_score: int, n: float) -> None:
    from app.scoring.engine import nutrition_value

    assert nutrition_value(ns_score, "general", -17, 55, CFG) == pytest.approx(n, abs=1e-3)


@spec("ENGINE-1")
def test_nutrition_value_falls_as_the_nutri_score_rises() -> None:
    from app.scoring.engine import nutrition_value

    values = [nutrition_value(s, "general", -17, 55, CFG) for s in range(-17, 56)]
    assert values == sorted(values, reverse=True)
    drinks = [nutrition_value(s, "beverage", -7, 40, CFG) for s in (-7, 2, 6, 9, 40)]
    assert drinks[0] == 1.0 and drinks[-1] == 0.0 and drinks == sorted(drinks, reverse=True)


@spec("ENGINE-14")
def test_good_nutrition_is_not_capped() -> None:
    lean = {**SNACK, "sugars_g": 1, "saturated_fat_g": 0.5, "salt_g": 0.1, "energy_kj": 600}
    r = score(facts(nova=1, **lean))
    assert r.nutriscore["grade"] in ("a", "b") and r.total is not None and r.total > 49
    assert not any(ln.rule_id == "nutrition.cap" for ln in r.breakdown)


@spec("ENGINE-1")
def test_water_has_full_nutrition_value() -> None:
    r = score(facts(tags=("en:mineral-waters",), nova=1))
    assert r.components["nutrition"]["value"] == 1.0
    assert r.total == 100


@spec("ENGINE-3")
def test_not_scored_still_returns_other_components() -> None:
    r = score(facts(nova=4, additives=(additive("e250", 2, "B"),), energy_kj=100))
    assert (r.status, r.total, r.band) == ("not_scored", None, None)
    assert r.components["additives"]["known"] and r.components["processing"]["known"]
    assert {"sugars_g", "saturated_fat_g", "salt_g"} <= set(r.missing_inputs)


@spec("ENGINE-5")
def test_unknown_component_rescales_weights() -> None:
    r = score(facts(nova=None, **SNACK))
    # (60 * 0.3875 + 30 * 1) / 90 * 100 = 59.2 -> 59 before the D cap
    assert (
        next(ln.input_value for ln in r.breakdown if ln.rule_id == "component.nutrition") == 0.3875
    )
    assert r.total == 49
    assert "nova_group" in r.missing_inputs
    assert not r.components["processing"]["known"]


@spec("ENGINE-5")
def test_unknown_additives_rescale_weights() -> None:
    r = score(facts(nova=4, additives=None, **SNACK))
    assert r.total == round(60 * 0.3875 / 70 * 100)  # 33, under the cap
    assert "additives" in r.missing_inputs


@spec("ENGINE-6")
def test_additive_cap_applies_after_total() -> None:
    r = score(facts(tags=("en:mineral-waters",), nova=1, additives=(additive("e171", 3, "A"),)))
    assert r.total == 49
    cap = next(ln for ln in r.breakdown if ln.rule_id == "additives.cap")
    assert cap.points < 0


@spec("ENGINE-7")
@pytest.mark.parametrize(
    ("total", "band"),
    [(0, "poor"), (24, "poor"), (25, "mediocre"), (49, "mediocre"), (50, "good"),
     (74, "good"), (75, "excellent"), (100, "excellent")],
)  # fmt: skip
def test_bands(total: int, band: str) -> None:
    b = band_for(total, CFG)
    assert b["id"] == band and b["label"]


@spec("ENGINE-8")
def test_every_line_has_rule_and_source() -> None:
    r = score(facts(nova=3, additives=(additive("e250", 2, "B"), additive("e330")), **SNACK))
    for line in r.breakdown:
        d = line.to_dict()
        assert set(d) >= {"rule_id", "component", "points", "input_value", "source_url",
                          "estimated"}  # fmt: skip
        assert d["rule_id"] and d["source_url"]


@spec("ENGINE-9")
def test_component_lines_add_up_to_total() -> None:
    r = score(facts(nova=3, additives=(additive("e250", 2, "B"),), **SNACK))
    parts = [ln.points for ln in r.breakdown if ln.rule_id.startswith("component.")]
    caps = [ln.points for ln in r.breakdown if ln.rule_id.endswith(".cap")]
    assert len(parts) == 3
    assert round(sum(parts)) + sum(caps) == r.total


@spec("ENGINE-10")
def test_confidence() -> None:
    assert score(facts(nova=4, **SNACK)).confidence == 1.0
    partial = {k: v for k, v in SNACK.items() if k != "fiber_g"}
    # 9 inputs: fibre and NOVA missing, fvl estimated -> 6/9
    r = score(facts(nova=None, estimated=("fvl_percent",), **partial))
    assert r.confidence == 0.67


@spec("ENGINE-11")
def test_engine_version_from_config() -> None:
    assert score(facts(**SNACK)).engine_version == CFG.engine_version


@spec("ENGINE-12")
def test_explain_is_template_text_without_banned_words() -> None:
    r = score(facts(nova=4, additives=(additive("e250", 3, "A", "Sodium nitrite"),), **SNACK))
    sentences = explain(r)
    assert sentences[0].startswith("Scores ")
    assert any("Sodium nitrite" in s for s in sentences)
    assert not any(w in s.lower() for s in sentences for w in BANNED)


@spec("ENGINE-12")
def test_explain_not_scored() -> None:
    sentences = explain(score(facts(energy_kj=100)))
    assert sentences[0].startswith("Not scored")


@spec("PROC-5")
def test_organic_gives_no_points() -> None:
    plain = score(facts(nova=4, **SNACK))
    organic = score(facts(nova=4, tags=("en:organic",), **SNACK))
    assert plain.total == organic.total


# --- Determinism and bounds (ENGINE-2, ENGINE-4) ---

_nutrient = st.floats(min_value=0, max_value=4000, allow_nan=False, allow_infinity=False)
_tags = st.sampled_from([(), ("en:beverages",), ("en:cheeses",), ("en:olive-oils",),
                         ("en:beef",), ("en:mineral-waters",)])  # fmt: skip
_additive = st.builds(
    AdditiveInfo,
    code=st.sampled_from(["e100", "e250", "e330", "e951", "e171"]),
    name=st.just("x"),
    risk_level=st.one_of(st.none(), st.integers(0, 3)),
    evidence_grade=st.one_of(st.none(), st.sampled_from(["A", "B", "C"])),
)
_facts = st.builds(
    ProductFacts,
    nutrients=st.dictionaries(
        st.sampled_from(
            [
                "energy_kj",
                "sugars_g",
                "saturated_fat_g",
                "fat_g",
                "salt_g",
                "fiber_g",
                "proteins_g",
                "fvl_percent",
            ]
        ),
        st.builds(Nutrient, _nutrient, st.booleans()),
    ),
    category_tags=_tags,
    nova_group=st.one_of(st.none(), st.integers(0, 5)),
    additives=st.one_of(st.none(), st.lists(_additive, max_size=5).map(tuple)),
)


@spec("ENGINE-2", "ENGINE-4")
@settings(max_examples=300, deadline=None)
@given(_facts)
def test_total_is_bounded_and_deterministic(f: ProductFacts) -> None:
    a, b = score(f), score(f)
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)
    if a.total is not None:
        assert 0 <= a.total <= 100 and isinstance(a.total, int)


@spec("ENGINE-4", "ADD-4")
@settings(max_examples=100, deadline=None)
@given(st.lists(_additive, min_size=2, max_size=5, unique_by=lambda a: a.code))
def test_additive_order_does_not_matter(adds: list[AdditiveInfo]) -> None:
    shuffled = adds[:]
    random.Random(0).shuffle(shuffled)
    a = score(facts(nova=3, additives=tuple(adds), **SNACK)).to_dict()
    b = score(facts(nova=3, additives=tuple(shuffled), **SNACK)).to_dict()
    assert a == b


@spec("ENGINE-13")
@pytest.mark.parametrize(
    ("value", "unit", "shown"),
    [(1009.73, "kJ", "1010"), (9.7345, "g", "9.7"), (20.354, "g", "20.4"), (0.8036, "g", "0.8"),
     (0.05, "g", "0.05"), (12.0, "g", "12"), (45.06, "%", "45.1"), (0.0, "%", "0")],
)  # fmt: skip
def test_numbers_in_sentences_are_rounded_for_reading(value: float, unit: str, shown: str) -> None:
    from app.scoring.explain import display_number

    assert display_number(value, unit) == shown


@spec("ENGINE-13")
def test_explanations_never_show_raw_float_noise() -> None:
    cfg = default_config()
    noisy = facts(**{**SNACK, "sugars_g": 20.354, "saturated_fat_g": 9.7345})
    sentences = " ".join(explain(score(noisy, cfg)))
    assert "20.354" not in sentences and "9.7345" not in sentences
    assert "9.7 g" in sentences


CANDY: dict[str, Any] = {
    "energy_kj": 1953, "sugars_g": 46.7, "saturated_fat_g": 15, "fat_g": 25, "salt_g": 0.29,
    "fiber_g": 1.7, "proteins_g": 10, "fvl_percent": 5.5,
}  # fmt: skip


@spec("ENGINE-15")
def test_in_short_leads_with_the_verdict_and_the_cap() -> None:
    adds = (
        additive("e322", None, "C", "E322 - Lecithins"),
        additive("e414", None, "C", "E414 - Acacia gum"),
    )
    r = score(facts(nova=4, additives=adds, **CANDY))
    sentences = explain(r)
    assert sentences[0] == f"Scores {r.total} out of 100 ({r.band['label'] if r.band else ''})."
    assert sentences[1] == "Nutrition: very poor (Nutri-Score E, scored as a general food)."
    assert sentences[2] == "High in sugars (46.7 g) and saturated fat (15 g) per 100 g."
    assert "2 additives, none with an EFSA risk rating." in sentences
    assert "Ultra-processed (NOVA 4)." in sentences
    assert r.total is not None and r.total < 50  # a candy bar is never "Good"


@spec("ENGINE-15")
def test_in_short_names_good_sources_and_capping_additives() -> None:
    lean = {**SNACK, "sugars_g": 1, "saturated_fat_g": 0.5, "salt_g": 0.1, "energy_kj": 600,
            "fiber_g": 9, "proteins_g": 14}  # fmt: skip
    sentences = explain(score(facts(nova=1, additives=(), **lean)))
    assert "Good source of" in " ".join(sentences) and "No additives." in sentences
    assert "Unprocessed or minimally processed (NOVA 1)." in sentences
    nitrite = additive("e250", 3, "A", "E250 - Sodium nitrite")
    capped = explain(score(facts(nova=3, additives=(nitrite,), **lean)))
    assert (
        "E250 - Sodium nitrite has a high EFSA overexposure rating, so the score is capped."
        in capped
    )


@spec("ENGINE-14", "ENGINE-15")
def test_in_short_explains_the_nutri_score_cap() -> None:
    r = score(facts(nova=1, additives=(), **SNACK))  # a D that would otherwise score above 49
    assert r.total == 49
    assert (
        explain(r)[0]
        == "Scores 49 out of 100 (Mediocre). Capped at 49 because its Nutri-Score is D."
    )
