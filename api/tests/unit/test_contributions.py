from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.services.contributions import ContributionIn, RateLimiter, off_fields, product_row

spec = pytest.mark.spec
NOW = datetime(2026, 10, 12, tzinfo=UTC)
NUTRITION = {"energy_kj": 1750, "sugars_g": 21.8, "saturated_fat_g": 1.8, "salt_g": 0.73,
             "fat_g": 14.5, "fiber_g": 7.3, "proteins_g": 5.5}  # fmt: skip


def body(**kw: Any) -> ContributionIn:
    base = {"gtin": "0000000000017", "name": "Granola", "brand": "Acme", "kind": "food",
            "nutrition": NUTRITION}  # fmt: skip
    return ContributionIn.model_validate({**base, **kw})


@spec("CONTRIB-4")
@pytest.mark.parametrize(
    "nutrition",
    [{**NUTRITION, "energy_kj": 3801}, {**NUTRITION, "sugars_g": -1},
     {**NUTRITION, "salt_g": 101}, {**NUTRITION, "saturated_fat_g": 20, "fat_g": 10},
     {k: v for k, v in NUTRITION.items() if k != "salt_g"}],
)  # fmt: skip
def test_values_outside_physical_limits_or_missing_are_rejected(nutrition: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        body(nutrition=nutrition)


@spec("CONTRIB-4")
@pytest.mark.parametrize(
    ("kind", "tags"),
    [("food", []), ("drink", ["en:beverages"]), ("cheese", ["en:cheeses"]),
     ("fat_oil_nut_seed", ["en:fats"])],
)  # fmt: skip
def test_kind_sets_the_category_tag(kind: str, tags: list[str]) -> None:
    assert product_row("0000000000017", body(kind=kind), NOW)["categories"] == tags


@spec("CONTRIB-6")
def test_the_product_row_credits_the_contribution_for_every_field() -> None:
    row = product_row("0000000000017", body(ingredients_text="  Oats, honey "), NOW)
    assert row["nutrition"]["salt_g"] == {"value": 0.73, "estimated": False}
    assert row["ingredients_text"] == "Oats, honey"
    assert set(row["source_by_field"].values()) == {"contribution"}
    assert row["additives_known"] is False and row["nova_group"] is None


@spec("CONTRIB-8")
def test_rate_limit_is_per_key_per_hour() -> None:
    clock = [0.0]
    limiter = RateLimiter(2, clock=lambda: clock[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")  # other clients aren't affected
    clock[0] = 3600
    assert limiter.allow("a")  # the hour has passed


@spec("CONTRIB-10")
def test_fields_sent_to_open_food_facts_are_per_100g_and_skip_blanks() -> None:
    fields = off_fields("0000000000017", body(brand=None))
    assert fields["nutrition_data_per"] == "100g" and fields["nutriment_salt"] == "0.73"
    assert fields["nutriment_energy-kj_unit"] == "kJ" and "brands" not in fields
