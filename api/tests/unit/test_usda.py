import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from app.services.off_mapping import map_product as map_off_product
from app.services.usda_client import USDAClient
from app.services.usda_mapping import (
    UsdaFood,
    category_key,
    category_map,
    fill_gaps,
    map_nutrition,
    map_product,
)
from pipeline.usda_bulk import gtin_of, load_fill, read_fill, save_fill

spec = pytest.mark.spec
NOW = datetime(2026, 10, 12, tzinfo=UTC)
GTIN = "0051000198808"
UA = "FoodTrace/0.1 (tests@example.com)"
BROTH = {1008: 4.0, 2000: 0.43, 1258: 0.0, 1093: 353.0, 1004: 0.0, 1079: 0.0, 1003: 0.85}


def food(**kw: object) -> UsdaFood:
    base: dict[str, object] = {"description": "Swanson Beef Broth", "brand": "SWANSON",
                               "ingredients": "BEEF STOCK, SALT", "category": "Canned Soup",
                               "nutrients": dict(BROTH)}  # fmt: skip
    return UsdaFood(**{**base, **kw})  # type: ignore[arg-type]


@spec("USDA-1")
def test_nutrients_map_per_100g_with_kcal_and_sodium_converted() -> None:
    n = map_nutrition(BROTH)
    assert n["energy_kj"]["value"] == pytest.approx(16.736)
    assert n["salt_g"]["value"] == pytest.approx(0.8825)
    assert n["sugars_g"] == {"value": 0.43, "estimated": False}
    assert map_nutrition({1062: 100.0, 1008: 999.0})["energy_kj"]["value"] == 100.0  # kJ wins


@spec("USDA-1")
def test_unparseable_or_negative_amounts_are_missing() -> None:
    from app.services.usda_mapping import to_number

    assert to_number("x") is None and to_number(-1) is None and to_number("2.5") == 2.5


@spec("USDA-2")
def test_categories_map_to_off_tags_plus_a_usda_slug() -> None:
    cats = category_map()
    assert cats.categories("Soda") == ["en:beverages", "en:sodas", "usda:soda"]
    assert cats.categories("Cheese")[0] == "en:cheeses"
    assert cats.categories("Candy") == ["en:confectioneries", "usda:candy"]
    assert cats.categories("Herbs & Spices") == ["usda:herbs-spices"]  # unmapped: general food
    assert category_key("Non Alcoholic Beverages  Ready to Drink") == category_key(
        "Non Alcoholic Beverages \u2013 Ready to Drink"
    )


@spec("USDA-3")
def test_out_of_scope_categories_are_excluded() -> None:
    cats = category_map()
    assert cats.is_excluded("Alcohol") and cats.is_excluded("Baby/Infant \u2013 Foods/Beverages")
    assert not cats.is_excluded("Cheese") and not cats.is_excluded(None)


@spec("USDA-8")
def test_a_usda_only_product_row() -> None:
    row = map_product(GTIN, food(category="Soda"), NOW)
    assert row["name"] == "Swanson Beef Broth" and row["brand"] == "SWANSON"
    assert row["primary_category"] == "usda:soda" and "en:beverages" in row["categories"]
    assert row["additives_known"] is False and row["nova_group"] is None
    assert set(row["source_by_field"].values()) == {"usda"}


@spec("USDA-5")
def test_gaps_are_filled_but_off_values_are_never_replaced() -> None:
    off = map_off_product(GTIN, {"product_name": "Broth", "nutriments": {"sugars_100g": 1.0}}, NOW)
    before = off["completeness"]
    filled = fill_gaps(off, food())
    assert off["nutrition"]["sugars_g"]["value"] == 1.0  # OFF kept
    assert off["nutrition"]["salt_g"]["value"] == pytest.approx(0.8825)  # USDA filled
    assert off["source_by_field"]["nutrition.salt_g"] == "usda"
    assert "nutrition.sugars_g" not in off["source_by_field"]
    assert off["ingredients_text"] == "BEEF STOCK, SALT"
    assert off["source_by_field"]["ingredients_text"] == "usda"
    assert filled == 7 and off["completeness"] > before


def _zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(f"FoodData_Central_branded_food_csv_2025-12-18/{name}", text)
    return path


def csv_line(*fields: str) -> str:
    return ",".join(f'"{f}"' for f in fields) + "\n"


BRANDED_HEADER = ('"fdc_id","brand_owner","brand_name","gtin_upc","ingredients",'
                  '"branded_food_category","modified_date","available_date","market_country",'
                  '"discontinued_date"\n')  # fmt: skip


@spec("USDA-4")
def test_bulk_reads_the_zip_in_place_and_keeps_the_latest_record(tmp_path: Path) -> None:
    us, soup = "United States", "Canned Soup"
    branded = BRANDED_HEADER + "".join(csv_line(*r) for r in [
        ("1", "CAMPBELL", "SWANSON", "00051000198808", "OLD", soup, "", "2020-01-01", us, ""),
        ("2", "CAMPBELL", "SWANSON", "00051000198808", "NEW", soup, "", "2024-01-01", us, ""),
        ("3", "X", "", "00051000198808", "GONE", soup, "", "2025-01-01", us, "2025-02-01"),
        ("4", "Y", "", "00036000291452", "", soup, "", "2024-01-01", "Canada", ""),
        ("5", "Z", "", "00012345678905", "", "Alcohol", "", "2024-01-01", us, ""),
        ("6", "W", "", "00099999999993", "", "Candy", "", "2024-01-01", us, ""),
    ])  # fmt: skip
    foods = '"fdc_id","data_type","description"\n"1","b","Old name"\n"2","b","New name"\n'
    nutrients = ('"id","fdc_id","nutrient_id","amount"\n"10","2","2000","0.43"\n'
                 '"11","2","1093","353"\n"12","2","1087","9"\n"13","1","2000","99"\n')  # fmt: skip
    path = _zip(tmp_path / "branded.zip", {"branded_food.csv": branded, "food.csv": foods,
                                            "food_nutrient.csv": nutrients})  # fmt: skip
    wanted = {GTIN, "0036000291452", "0012345678905"}  # 0099999999993 isn't in the OFF extract
    fill = read_fill(path, wanted)
    assert set(fill) == {GTIN}  # Canada and excluded alcohol dropped
    assert fill[GTIN] == UsdaFood("New name", "SWANSON", "NEW", "Canned Soup",
                                  {2000: 0.43, 1093: 353.0})  # fmt: skip
    save_fill(fill, tmp_path / "fill.json.gz")
    assert load_fill(tmp_path / "fill.json.gz") == fill


@spec("USDA-4")
def test_usda_gtins_are_normalized_from_14_digits() -> None:
    assert gtin_of("00051000198808") == GTIN
    assert gtin_of("4006381333931") == "4006381333931"
    assert gtin_of("00051000198809") is None and gtin_of("abc") is None


@spec("USDA-6")
def test_a_product_that_is_only_scorable_with_usda_is_imported(tmp_path: Path) -> None:
    from pipeline.off_bulk import mapped_rows

    from ..pipeline.export_rows import export_row, write_extract

    extract = write_extract(
        tmp_path, [export_row(GTIN, **{"saturated-fat_100g": "", "salt_100g": ""})]
    )
    assert mapped_rows(extract, NOW) == []
    stats: dict[str, int] = {}
    [(row, _, _)] = mapped_rows(extract, NOW, usda={GTIN: food()}, stats=stats)
    assert row["source_by_field"]["nutrition.salt_g"] == "usda"
    assert stats["usda_products"] == 1


def search_hit(gtin_upc: str = "00051000198808", **kw: object) -> dict[str, object]:
    return {"fdcId": 1, "description": "Swanson Beef Broth", "gtinUpc": gtin_upc,
            "brandOwner": "CAMPBELL", "brandName": "SWANSON", "ingredients": "BEEF STOCK",
            "brandedFoodCategory": "Canned Soup", "publishedDate": "2026-07-23",
            "foodNutrients": [{"nutrientId": k, "value": v} for k, v in BROTH.items()],
            **kw}  # fmt: skip


@spec("USDA-7", "USDA-10")
async def test_live_search_uses_the_14_digit_gtin_our_key_and_user_agent() -> None:
    async with httpx.AsyncClient() as http, respx.mock(base_url="https://usda.test") as mock:
        route = mock.get("/fdc/v1/foods/search").respond(
            200, json={"foods": [search_hit("00051000198800"), search_hit()]}
        )
        found = await USDAClient(http, "https://usda.test", "KEY", UA).fetch(GTIN)
    assert found is not None and found.description == "Swanson Beef Broth"
    req = route.calls.last.request
    assert req.url.params["query"] == "00051000198808" and req.url.params["api_key"] == "KEY"
    assert req.url.params["dataType"] == "Branded" and req.headers["user-agent"] == UA


@spec("USDA-7")
async def test_only_a_matching_gtin_counts_and_the_newest_wins() -> None:
    hits = [search_hit(description="Old", publishedDate="2020-01-01"),
            search_hit(description="New", publishedDate="2026-01-01"),
            search_hit("00036000291452", description="Other")]  # fmt: skip
    async with httpx.AsyncClient() as http, respx.mock(base_url="https://usda.test") as mock:
        mock.get("/fdc/v1/foods/search").respond(200, json={"foods": hits})
        found = await USDAClient(http, "https://usda.test", "KEY", UA).fetch(GTIN)
    assert found is not None and found.description == "New"


@spec("USDA-3", "USDA-9")
@pytest.mark.parametrize(
    "respond",
    [lambda r: r.respond(429), lambda r: r.respond(500),
     lambda r: r.mock(side_effect=httpx.ConnectTimeout("t")),
     lambda r: r.respond(200, json={"foods": []}),
     lambda r: r.respond(200, json={"foods": [search_hit(brandedFoodCategory="Alcohol")]})],
)  # fmt: skip
async def test_failures_misses_and_excluded_categories_are_not_found(respond: object) -> None:
    async with httpx.AsyncClient() as http, respx.mock(base_url="https://usda.test") as mock:
        respond(mock.get("/fdc/v1/foods/search"))  # type: ignore[operator]
        assert await USDAClient(http, "https://usda.test", "KEY", UA).fetch(GTIN) is None
