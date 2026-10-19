import pytest

from app.scoring.config import default_config
from app.scoring.engine import score
from app.scoring.explain import explain
from app.scoring.ingredients import (
    Ingredient,
    estimate_fvl,
    estimate_nova,
    find_additive_codes,
    split_ingredients,
)

from .factories import SNACK, facts

spec = pytest.mark.spec
CFG = default_config()
EST = CFG.estimates


def names(text: str) -> list[str]:
    return [i.name for i in split_ingredients(text)]


@spec("EST-1")
def test_split_at_top_level_commas_keeping_sub_ingredients_and_percentages() -> None:
    parsed = split_ingredients(
        "INGREDIENTS: Tomatoes (45%), chocolate (sugar, cocoa butter), 12% onions; salt."
    )
    assert [i.name for i in parsed] == ["tomatoes", "chocolate", "onions", "salt"]
    assert [i.percent for i in parsed] == [45.0, None, 12.0, None]
    assert parsed[1].text == "chocolate (sugar, cocoa butter)"
    assert split_ingredients(None) == [] and split_ingredients("  ") == []


@spec("EST-1")
def test_decimal_commas_and_brackets_of_every_kind() -> None:
    parsed = split_ingredients("Mango [40,5%], water {filtered}")
    assert parsed[0].percent == 40.5 and [i.name for i in parsed] == ["mango", "water"]


@spec("EST-2")
def test_fvl_is_the_sum_of_stated_percentages_a_lower_bound() -> None:
    parsed = split_ingredients("Tomatoes (45%), carrots (10%), onions, sugar (5%)")
    assert estimate_fvl(parsed, EST) == 55.0  # unstated onions count as 0


@spec("EST-2")
def test_single_fruit_or_vegetable_is_100_and_derivatives_never_count() -> None:
    assert estimate_fvl(split_ingredients("Peas."), EST) == 100.0
    assert estimate_fvl(split_ingredients("Potatoes (90%), salt"), EST) == 0.0
    assert estimate_fvl(split_ingredients("Tomato paste powder (50%), salt"), EST) == 0.0
    assert estimate_fvl(split_ingredients("Apple juice concentrate (30%), water"), EST) == 0.0
    assert estimate_fvl([], EST) is None


@spec("EST-2")
def test_fvl_estimate_is_capped_at_100() -> None:
    parsed = [Ingredient("apples", "apples", 80.0), Ingredient("pears", "pears", 40.0)]
    assert estimate_fvl(parsed, EST) == 100.0


@spec("EST-3")
@pytest.mark.parametrize(
    ("text", "group", "marker"),
    [
        ("Peanuts.", 1, None),
        ("Water, oats.", 1, None),  # water is ignored
        ("Sea salt.", 2, None),
        ("Olive oil, salt.", 2, None),
        ("Tomatoes, salt.", 3, None),
        ("Cucumbers, water, vinegar, salt.", 3, None),
        ("Corn, high fructose corn syrup, salt.", 4, "high fructose corn syrup"),
        ("Oats, sugar, natural flavors.", 4, "natural flavors"),
        ("Milk, cheese culture, salt, annatto (color).", 4, "annatto"),
    ],
)
def test_nova_from_ingredient_markers(text: str, group: int, marker: str | None) -> None:
    est = estimate_nova(split_ingredients(text), EST)
    assert est is not None and (est.group, est.marker) == (group, marker)


@spec("EST-3")
def test_no_ingredients_means_no_nova_estimate() -> None:
    assert estimate_nova([], EST) is None
    assert estimate_nova(split_ingredients("Water."), EST) is None


@spec("EST-4", "EST-7")
def test_engine_uses_estimates_only_for_missing_inputs_and_flags_them() -> None:
    no_fvl = {k: v for k, v in SNACK.items() if k != "fvl_percent"}
    text = "Oats (60%), apples (30%), sugar, natural flavor"
    result = score(
        facts(nova=None, **no_fvl).__class__(
            nutrients=facts(**no_fvl).nutrients, ingredients_text=text, additives=()
        ),
        CFG,
    )
    lines = {ln.rule_id: ln for ln in result.breakdown}
    fvl = lines["nutriscore.general.fvl"]
    assert fvl.input_value == 30.0 and fvl.estimated
    nova = lines["processing.nova"]
    assert nova.input_value == 4 and nova.estimated
    assert nova.note == ('NOVA 4: ultra-processed food, estimated from the ingredient list '
                         '("natural flavor").')  # fmt: skip
    assert "nova_group" not in result.missing_inputs and result.components["processing"]["known"]
    sentences = " ".join(explain(result))
    assert "NOVA 4, estimated from the ingredient list" in sentences  # flagged once, not twice


@spec("EST-6", "EST-7")
def test_stated_values_win_and_estimates_never_raise_confidence() -> None:
    stated = facts(nova=1, additives=(), **SNACK)
    with_text = stated.__class__(
        **{**stated.__dict__, "ingredients_text": "Corn syrup, apples (90%)"}
    )
    a, b = score(stated, CFG), score(with_text, CFG)
    assert a.to_dict() == b.to_dict()  # nothing missing, so the text changes nothing

    bare = facts(additives=(), **{k: v for k, v in SNACK.items() if k != "fvl_percent"})
    estimated = bare.__class__(**{**bare.__dict__, "ingredients_text": "Apples (90%), sugar"})
    assert score(estimated, CFG).confidence == score(bare, CFG).confidence
    assert score(estimated, CFG).to_dict() == score(estimated, CFG).to_dict()  # deterministic


@spec("EST-5")
def test_additives_are_found_by_name_or_e_number_as_whole_words() -> None:
    names_ = {"e250": "E250 - Sodium nitrite", "e330": "E330 - Citric acid",
              "e300": "E300 - Ascorbic acid", "e1": "E1 - Salt"}  # fmt: skip
    text = "PORK, WATER, SALT, SODIUM NITRITE, E300, CITRIC ACIDS"
    assert find_additive_codes(text, names_) == ["e1", "e250", "e300"]
    assert find_additive_codes(None, names_) == []
