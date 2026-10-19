from pathlib import Path

import httpx
import pytest
import respx

from pipeline.fda_status import (
    EXPORT_URL,
    UsStatus,
    additive_name,
    download,
    normalize_name,
    parse,
    status_of,
)
from pipeline.reference import add_us_status

spec = pytest.mark.spec
HEADER = ('CAS Reg No (or other ID),Substance,Other Names,Used for (Technical Effect),Reg col01,'
          'Reg add01,Reg add02,Reg prohibited189,Reg Administrative,FEMA No\n')  # fmt: skip
EXPORT = (
    "Downloaded from FDA Substances Added to Food; Last updated 7/28/2026.\n\n"
    '"It is important to note that the inventory is only a partial list."\n\n'
    + HEADER
    + '" 7632-00-0"," SODIUM NITRITE"," &diams; NITROUS ACID, SODIUM SALT"," PRESERVATIVE",,'
    '=T("172.170"),=T("175.105"),,,\n'
    '" 77-92-9"," CITRIC ACID"," &diams; CITRIC ACID<br />&diams; 2-HYDROXY-1,2,3-'
    'PROPANETRICARBOXYLIC ACID"," SEQUESTRANT",=T("73.85"),=T("184.1033"),,,,=T("2306")\n'
    '" 1-1"," FD&C RED NO. 3, ALUMINUM LAKE--DELISTED",,," COLOR",=T("81.10"),,,,,\n'
    '" 2-2"," CALAMUS"," &diams; SWEET FLAG",,,,,=T("189.110"),,\n'
    '" 3-3"," PACKAGING RESIN",,,,=T("177.1210"),,,,\n'
    '" 4-4"," ACETAL",,,,,,,,=T("2002")\n'
)  # fmt: skip


@spec("FDA-2")
@pytest.mark.parametrize(
    ("substance", "sections", "fema", "expected"),
    [
        ("SODIUM NITRITE", ["172.170", "175.105"], "", UsStatus("food_additive", "172.170")),
        ("CITRIC ACID", ["73.85", "184.1033"], "2306", UsStatus("color_additive", "73.85")),
        ("POTASSIUM SORBATE", ["182.3640"], "", UsStatus("gras", "182.3640")),
        ("X", ["181.33"], "", UsStatus("prior_sanctioned", "181.33")),
        ("CALAMUS", ["172.1", "189.110"], "", UsStatus("prohibited", "189.110")),
        ("FD&C RED NO. 3, LAKE--DELISTED", ["74.303"], "", UsStatus("delisted", None)),
        ("ACETAL", [], "2002", UsStatus("gras_flavor", None)),
        ("PACKAGING RESIN", ["177.1210"], "", None),  # indirect-only: no status
    ],
)
def test_status_comes_from_the_highest_priority_cfr_part(
    substance: str, sections: list[str], fema: str, expected: UsStatus | None
) -> None:
    assert status_of(substance, sections, fema) == expected


@spec("FDA-2", "FDA-3")
def test_the_export_is_parsed_past_its_preamble_with_other_names() -> None:
    index = parse(EXPORT)
    assert index["sodium nitrite"] == UsStatus("food_additive", "172.170")
    assert index["nitrous acid sodium salt"] == UsStatus("food_additive", "172.170")
    assert index["2 hydroxy 1 2 3 propanetricarboxylic acid"].status == "color_additive"
    assert index["sweet flag"] == UsStatus("prohibited", "189.110")
    assert index["fd c red no 3 aluminum lake delisted"].status == "delisted"
    assert "packaging resin" not in index


@spec("FDA-3")
def test_names_are_matched_without_e_numbers_case_or_punctuation() -> None:
    assert additive_name("E250 - Sodium nitrite") == "sodium nitrite"
    assert additive_name("E160a(ii) - Beta-carotene") == "beta carotene"
    assert normalize_name(" FD&amp;C  Red No. 40 ") == "fd c red no 40"


@spec("FDA-3", "FDA-4")
def test_additives_get_a_status_only_on_an_exact_name_match() -> None:
    rows = [{"name": "E250 - Sodium nitrite"}, {"name": "E330 - Citric acid"},
            {"name": "E250 - Sodium nitrites"}]  # fmt: skip
    assert add_us_status(rows, parse(EXPORT)) == 2
    assert rows[0]["us_status"] == "food_additive" and rows[0]["fda_cfr_ref"] == "172.170"
    assert rows[2]["us_status"] is None and rows[2]["fda_cfr_ref"] is None


@spec("FDA-1")
def test_download_saves_the_export_with_our_user_agent(tmp_path: Path) -> None:
    with respx.mock as mock:
        route = mock.get(EXPORT_URL).respond(200, text=EXPORT)
        path = download("FoodTrace/0.1 (t@example.com)", tmp_path / "fda.csv")
    assert path.read_text() == EXPORT
    request: httpx.Request = route.calls.last.request
    assert request.headers["user-agent"] == "FoodTrace/0.1 (t@example.com)"


@spec("FDA-7")
def test_a_non_inventory_response_is_rejected_and_not_cached(tmp_path: Path) -> None:
    from pipeline.fda_status import FDAUnavailable

    cache = tmp_path / "fda.csv"
    with respx.mock as mock:
        mock.get(EXPORT_URL).respond(200, text="<html>Access denied</html>")
        with pytest.raises(FDAUnavailable):
            download("UA", cache)
        mock.get(EXPORT_URL).respond(503)
        with pytest.raises(FDAUnavailable):
            download("UA", cache)
    assert not cache.exists()
    with pytest.raises(FDAUnavailable):
        parse("<html>not the export</html>")


@spec("FDA-7")
def test_the_reference_load_carries_on_without_fda(tmp_path: Path) -> None:
    from pipeline.reference import us_status_index

    with respx.mock as mock:
        mock.get(EXPORT_URL).respond(200, text="<html>blocked</html>")
        assert us_status_index(True, "UA", tmp_path / "fda.csv") is None
        mock.get(EXPORT_URL).respond(200, text=EXPORT)
        index = us_status_index(True, "UA", tmp_path / "fda.csv")
    assert index is not None and index["sodium nitrite"].status == "food_additive"
