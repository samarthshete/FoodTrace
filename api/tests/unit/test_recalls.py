import io
import json
import zipfile
from datetime import date
from typing import Any

import httpx
import pytest
import respx

from app.db.models import Product, Recall
from app.scoring.config import default_config
from app.services.recalls import (
    eligible_brand,
    extract_codes,
    match,
    name_words,
    normalize_text,
    record_url,
)
from pipeline.recalls import DOWNLOAD_INDEX, download, rows_in_window, to_row, window_start

spec = pytest.mark.spec
CFG = default_config().recalls
GTIN = "0049000028911"  # UPC-A 049000028911


def product(name: str | None = "Crunchy Peanut Butter Bars", brand: str | None = "Acme Foods",
            gtin: str = GTIN) -> Product:  # fmt: skip
    return Product(gtin=gtin, name=name, brand=brand, categories=[])


def recall(description: str, firm: str = "Some Firm LLC", codes: list[str] | None = None) -> Recall:
    return Recall(recall_number="F-1-2026", product_description=description,
                  recalling_firm=firm, codes=codes or [])  # fmt: skip


def record(**overrides: Any) -> dict[str, Any]:
    base = {
        "recall_number": "F-0001-2026", "event_id": "1", "status": "Ongoing",
        "classification": "Class II", "recalling_firm": "Acme Foods Inc",
        "product_description": "Acme Foods Crunchy Peanut Butter Bars, UPC 0 49000 02891 1",
        "code_info": "Lot 1234", "more_code_info": "", "reason_for_recall": "Undeclared peanut",
        "recall_initiation_date": "20260801", "report_date": "20260901",
    }  # fmt: skip
    return {**base, **overrides}


@spec("RECALL-3")
def test_codes_are_found_across_spaces_and_hyphens_and_normalized() -> None:
    assert extract_codes("UPC 0 49000 02891 1") == [GTIN]
    assert extract_codes(None, "UPC: 049000-028911", "") == [GTIN]
    assert extract_codes("EAN 4006381333931") == ["4006381333931"]


@spec("RECALL-3")
def test_runs_with_a_bad_check_digit_or_wrong_length_are_dropped() -> None:
    assert extract_codes("UPC 049000028912") == []  # check digit off by one
    assert extract_codes("Lot 12345678901234 exp 20261001") == []  # 14 and 8 digits


@spec("RECALL-6")
def test_text_is_lowercased_without_accents_or_punctuation() -> None:
    assert normalize_text("Café-Brand's  CRÈME!") == "cafe brand s creme"


@spec("RECALL-6")
def test_name_words_skip_short_words_brand_words_and_stop_words() -> None:
    assert name_words("Acme Original Peanut Butter & Jelly Bars of Oats", "acme", CFG) == [
        "peanut", "butter", "jelly", "bars", "oats",
    ]  # fmt: skip


@spec("RECALL-5")
def test_code_match_wins_even_without_brand() -> None:
    assert match(product(brand=None), recall("Something else", codes=[GTIN]), CFG) == "code"


@spec("RECALL-6")
def test_brand_and_two_name_words_match() -> None:
    hit = recall("Acme Foods peanut butter bars, 12 ct")
    assert match(product(), hit, CFG) == "brand_name"


@spec("RECALL-6")
def test_brand_in_the_firm_name_counts() -> None:
    hit = recall("Crunchy peanut bars", firm="Acme Foods, Inc.")
    assert match(product(), hit, CFG) == "brand_name"


@spec("RECALL-6")
def test_brand_alone_or_one_name_word_is_not_enough() -> None:
    assert match(product(), recall("Acme Foods chocolate cookies"), CFG) is None
    assert match(product(), recall("Acme Foods peanut cookies"), CFG) is None
    assert match(product(), recall("Peanut butter bars by Other Co"), CFG) is None


@spec("RECALL-6")
def test_brand_must_be_whole_words_and_only_the_first_brand_is_used() -> None:
    assert match(product(brand="Acme"), recall("Acmetown peanut butter bars"), CFG) is None
    p = product(brand="Acme Foods, Big Parent Co")
    assert match(p, recall("Big Parent Co peanut butter bars"), CFG) is None


@spec("RECALL-6")
def test_a_one_word_name_needs_that_one_word() -> None:
    assert match(product(name="Granola"), recall("Acme Foods granola, 8 oz"), CFG) == "brand_name"


@spec("RECALL-7")
def test_short_generic_or_missing_brands_and_names_only_match_by_code() -> None:
    text = "Great Value peanut butter bars"
    assert eligible_brand("Great Value", CFG) is None
    assert match(product(brand="Great Value"), recall(text), CFG) is None
    assert match(product(brand="AB"), recall("AB peanut butter bars"), CFG) is None
    assert match(product(name=None), recall("Acme Foods peanut butter bars"), CFG) is None
    assert match(product(brand="Great Value"), recall(text, codes=[GTIN]), CFG) == "code"


@spec("RECALL-9")
def test_record_url_is_the_openfda_query_for_the_recall_number() -> None:
    assert record_url("H-1395-2026") == (
        "https://api.fda.gov/food/enforcement.json?search=recall_number:%22H-1395-2026%22"
    )


@spec("RECALL-2", "RECALL-3")
def test_records_map_to_rows_with_dates_and_codes() -> None:
    row = to_row(record())
    assert row is not None
    assert row["recall_initiation_date"] == date(2026, 8, 1)
    assert row["report_date"] == date(2026, 9, 1)
    assert row["codes"] == [GTIN]
    assert to_row(record(recall_number="")) is None
    assert to_row(record(report_date="not a date")) is None


@spec("RECALL-2")
def test_only_records_reported_in_the_window_are_kept() -> None:
    today = date(2026, 10, 12)
    assert window_start(today, 3) == date(2023, 10, 12)
    assert window_start(date(2028, 2, 29), 3) == date(2025, 2, 28)
    kept = rows_in_window(
        [record(recall_number="new", report_date="20231012"),
         record(recall_number="old", report_date="20231011")],
        today, 3,
    )  # fmt: skip
    assert [r["recall_number"] for r in kept] == ["new"]


@spec("RECALL-1")
def test_download_uses_the_bulk_file_and_our_user_agent() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("food-enforcement-0001-of-0001.json", json.dumps({"results": [record()]}))
    file_url = (
        "https://download.open.fda.gov/food/enforcement/food-enforcement-0001-of-0001.json.zip"
    )
    index = {"results": {"food": {"enforcement": {"partitions": [{"file": file_url}]}}}}
    with respx.mock(assert_all_called=True) as mock:
        idx = mock.get(DOWNLOAD_INDEX).respond(200, json=index)
        zipped = mock.get(file_url).respond(200, content=buf.getvalue())
        records = download("FoodTrace/0.1 (tests@example.com)")
    assert records == [record()]
    for route in (idx, zipped):
        request: httpx.Request = route.calls.last.request
        assert request.headers["user-agent"] == "FoodTrace/0.1 (tests@example.com)"
