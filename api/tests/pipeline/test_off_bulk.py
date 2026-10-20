import gzip
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from pipeline.off_bulk import (
    INT_COLUMNS,
    NUTRIENT_COLUMNS,
    STRING_COLUMNS,
    TAG_COLUMNS,
    extract,
    mapped_rows,
    to_api_product,
)

from .export_rows import export_row, write_extract

spec = pytest.mark.spec
NOW = datetime(2026, 10, 12, tzinfo=UTC)
GTIN = "0036000291452"


@spec("OFF-1", "OFF-2")
def test_extract_keeps_us_rows_and_only_the_needed_columns(tmp_path: Path) -> None:
    islands = "en:united-states-minor-outlying-islands"  # not a substring match
    rows = [export_row(GTIN), export_row("4006381333931", countries_tags="en:germany"),
            export_row("0000000000017", countries_tags=islands)]  # fmt: skip
    out = pl.read_parquet(write_extract(tmp_path, rows))
    assert out["code"].to_list() == [GTIN]
    assert "countries_tags" not in out.columns and "url" not in out.columns
    assert out["categories_tags"].to_list() == [["en:snacks", "en:cereal-bars"]]
    assert out["sugars_100g"].to_list() == [12.0]


@spec("OFF-1")
def test_malformed_rows_are_skipped_not_fatal(tmp_path: Path) -> None:
    bad = export_row(GTIN, product_name="Oat\tBars")  # a stray tab shifts the columns
    out = pl.read_parquet(write_extract(tmp_path, [bad, export_row("0000000000017")]))
    assert out["code"].to_list() == ["0000000000017"]


@spec("OFF-3")
def test_rows_take_the_live_api_shape(tmp_path: Path) -> None:
    [row] = pl.read_parquet(write_extract(tmp_path, [export_row(GTIN)])).iter_rows(named=True)
    p = to_api_product(row)
    assert p["product_name"] == "Oat Bars" and p["ingredients_text"] == "Oats, sugar, citric acid"
    assert p["nutriments"]["sugars_100g"] == 12.0 and "fiber_100g" in p["nutriments"]
    assert "energy-kcal_100g" not in p["nutriments"]  # empty cells are missing, not zero
    assert p["additives_tags"] == ["en:e330"]


@spec("OFF-3")
def test_no_ingredients_and_no_additives_means_the_additive_list_is_unknown(
    tmp_path: Path,
) -> None:
    rows = [export_row(GTIN, ingredients_text="", additives_tags=""),
            export_row("0000000000017", additives_tags="")]  # fmt: skip
    items = mapped_rows(write_extract(tmp_path, rows), NOW)
    codes = {r["gtin"]: c for r, c, _ in items}
    assert codes == {GTIN: None, "0000000000017": []}


@spec("OFF-3", "OFF-4")
def test_mapping_matches_a_live_lookup(tmp_path: Path) -> None:
    [(row, codes, modified)] = mapped_rows(write_extract(tmp_path, [export_row(GTIN)]), NOW)
    assert row["name"] == "Oat Bars" and row["brand"] == "Acme Foods"
    assert row["primary_category"] == "en:cereal-bars"
    assert row["nutrition"]["salt_g"] == {"value": 0.9, "estimated": False}
    assert row["image_url"].endswith(f"/{GTIN}/front_en.12.400.jpg")
    assert codes == ["e330"]
    assert modified == datetime.fromtimestamp(1_760_000_000, UTC)


@spec("OFF-5")
def test_invalid_unnamed_or_unscorable_rows_are_skipped(tmp_path: Path) -> None:
    rows = [
        export_row("0036000291453"),  # bad check digit
        export_row("0000000000017", product_name=""),
        export_row("0000000000024", salt_100g=""),
        export_row("0000000000031"),
    ]
    items = mapped_rows(write_extract(tmp_path, rows), NOW)
    assert [r["gtin"] for r, _, _ in items] == ["0000000000031"]


@spec("OFF-5")
def test_a_duplicate_code_keeps_its_latest_edit(tmp_path: Path) -> None:
    rows = [
        export_row("036000291452", brands="New", last_modified_t="2000000000"),  # same GTIN
        export_row(GTIN, brands="Old", last_modified_t="1000000000"),
    ]
    [(row, _, _)] = mapped_rows(write_extract(tmp_path, rows), NOW)
    assert row["gtin"] == GTIN and row["brand"] == "New"


@spec("OFF-10")
def test_only_the_most_scanned_are_kept_above_the_cap(tmp_path: Path) -> None:
    rows = [export_row(g, unique_scans_n=n) for g, n in
            [("0000000000017", "5"), ("0000000000024", "50"), ("0000000000031", "20")]]  # fmt: skip
    items = mapped_rows(write_extract(tmp_path, rows), NOW, max_products=2)
    assert [r["gtin"] for r, _, _ in items] == ["0000000000024", "0000000000031"]


@spec("ACC-6")
def test_allergens_traces_and_diet_analysis_are_imported(tmp_path: Path) -> None:
    [(row, _, _)] = mapped_rows(write_extract(tmp_path, [export_row(GTIN)]), NOW)
    assert row["allergens"] == ["en:gluten", "en:milk"]
    assert row["traces"] == ["en:nuts"]
    assert row["ingredients_analysis"] == ["en:non-vegan", "en:vegetarian"]


@spec("OFF-12")
def test_renamed_export_columns_still_extract(tmp_path: Path) -> None:
    row = export_row(GTIN)
    header = [
        "code", "countries_tags", "product_name", "brands_en", "ingredients_text",
        "image_url", "categories_tags", "labels_tags", "additives_tags",
        "allergens_tags", "traces_tags", "ingredients_analysis_tags",
        *INT_COLUMNS, *NUTRIENT_COLUMNS, *STRING_COLUMNS,
    ]  # fmt: skip
    row["brands_en"] = row["brands"]
    row["allergens_tags"] = row["allergens"]
    source = tmp_path / "products.csv.gz"
    with gzip.open(source, "wt", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        f.write("\t".join(row.get(h, "") for h in header) + "\n")
    out = tmp_path / "us.parquet"
    extract(source, out)
    [(product, _, _)] = mapped_rows(out, NOW)
    assert product["brand"] == "Acme Foods"
    assert product["allergens"] == ["en:gluten", "en:milk"]


@spec("OFF-12")
def test_a_missing_optional_column_is_empty_not_fatal(tmp_path: Path) -> None:
    row = export_row(GTIN)
    header = [h for h in [
        "code", "countries_tags", "product_name", "ingredients_text", "image_url",
        *TAG_COLUMNS, *INT_COLUMNS, *NUTRIENT_COLUMNS, *STRING_COLUMNS,
    ] if h != "allergens"]  # fmt: skip
    source = tmp_path / "products.csv.gz"
    with gzip.open(source, "wt", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        f.write("\t".join(row.get(h, "") for h in header) + "\n")
    [(product, _, _)] = mapped_rows(extract(source, tmp_path / "us.parquet"), NOW)
    assert product["name"] == "Oat Bars" and product["brand"] is None
    assert product["allergens"] == []


@spec("ACC-6")
def test_an_extract_without_the_allergen_columns_is_rebuilt(tmp_path: Path) -> None:
    from pipeline.off_bulk import extract_outdated

    current = write_extract(tmp_path, [export_row(GTIN)])
    assert not extract_outdated(current, tmp_path / "missing.csv.gz")
    old = tmp_path / "old.parquet"
    pl.read_parquet(current).drop("allergens").write_parquet(old)
    assert extract_outdated(old, tmp_path / "missing.csv.gz")
    assert extract_outdated(tmp_path / "nope.parquet")
