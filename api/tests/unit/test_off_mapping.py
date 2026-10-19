from datetime import UTC, datetime

import pytest

from app.services.off_mapping import additive_codes, map_nutrition, map_product

spec = pytest.mark.spec
NOW = datetime(2026, 10, 12, tzinfo=UTC)


@spec("LOOKUP-13")
def test_energy_prefers_kj_then_kcal_then_generic() -> None:
    assert (
        map_nutrition({"energy-kj_100g": 500, "energy-kcal_100g": 1})["energy_kj"]["value"] == 500
    )
    assert map_nutrition({"energy-kcal_100g": 100})["energy_kj"]["value"] == 418.4
    assert map_nutrition({"energy_100g": 700})["energy_kj"]["value"] == 700


@spec("LOOKUP-13")
def test_salt_falls_back_to_sodium() -> None:
    assert map_nutrition({"salt_100g": 1.2, "sodium_100g": 9})["salt_g"]["value"] == 1.2
    assert map_nutrition({"sodium_100g": 0.4})["salt_g"]["value"] == 1.0


@spec("LOOKUP-13")
def test_fvl_declared_vs_estimated() -> None:
    declared = map_nutrition({"fruits-vegetables-legumes_100g": 50})["fvl_percent"]
    assert declared == {"value": 50, "estimated": False}
    estimated = map_nutrition({"fruits-vegetables-legumes-estimate-from-ingredients_100g": 30})
    assert estimated["fvl_percent"] == {"value": 30, "estimated": True}


@spec("LOOKUP-13")
@pytest.mark.parametrize("bad", ["n/a", "", None, True, [1]])
def test_unparseable_values_are_missing(bad: object) -> None:
    assert "sugars_g" not in map_nutrition({"sugars_100g": bad})


@spec("LOOKUP-13", "ADD-6")
def test_additive_list_known_vs_unknown() -> None:
    assert additive_codes({"additives_tags": ["en:e330", "en:e322i", "en:e330"]}) == [
        "e322i",
        "e330",
    ]
    assert additive_codes({"ingredients_text": "water, salt"}) == []
    assert additive_codes({}) is None


@spec("LOOKUP-13")
def test_map_product_fields() -> None:
    row = map_product(
        "0036000291452",
        {"product_name": " Oat Bars ", "brands": "Acme, Other", "nova_group": 9,
         "categories_tags": ["en:snacks", "en:cereal-bars"], "labels_tags": ["en:organic"],
         "nutriments": {"sugars_100g": 5}},
        NOW,
    )  # fmt: skip
    assert row["name"] == "Oat Bars" and row["brand"] == "Acme"
    assert row["nova_group"] is None  # out of range is missing
    assert row["primary_category"] == "en:cereal-bars"
    assert row["is_organic"] is True and row["additives_known"] is False
    assert row["source_by_field"]["name"] == "off" and "nova_group" not in row["source_by_field"]
