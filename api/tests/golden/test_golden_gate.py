from pathlib import Path

import polars as pl
import pytest

from app.scoring.config import default_config
from pipeline.golden import FULL, MIN_PRODUCTS, grade_rows, summarize, write_mismatches

spec = pytest.mark.spec
SAMPLE = Path(__file__).with_name("off_us_sample.parquet")


@pytest.fixture(scope="module")
def rows() -> list[dict[str, object]]:
    return list(pl.read_parquet(SAMPLE).iter_rows(named=True))


@spec("GOLD-2", "GOLD-5")
def test_our_grades_match_open_food_facts_on_99_percent(rows: list[dict[str, object]]) -> None:
    graded = grade_rows(rows, default_config())
    rate, _ = summarize(graded)
    assert len(graded) >= 2900, "the committed sample should almost all qualify"
    assert rate >= 0.99, f"golden gate: {rate:.2%} < 99%"


@spec("GOLD-1")
def test_only_products_with_an_off_grade_and_a_full_panel_are_graded(
    rows: list[dict[str, object]],
) -> None:
    row = dict(rows[0])
    assert len(grade_rows([{**row, "nutriscore_grade": "unknown"}], default_config())) == 0
    assert len(grade_rows([{**row, "fiber_100g": None}], default_config())) == 0
    assert "fiber_g" in FULL and len(grade_rows([row], default_config())) == 1


@spec("GOLD-3", "GOLD-4")
def test_mismatches_are_reported(rows: list[dict[str, object]], tmp_path: Path) -> None:
    graded = grade_rows(rows[:200], default_config())
    misses = write_mismatches(graded, tmp_path / "m.csv")
    lines = (tmp_path / "m.csv").read_text().splitlines()
    assert lines[0] == "code,name,class,our_grade,our_score,off_grade,off_score"
    assert len(lines) == misses + 1
    assert MIN_PRODUCTS == 2000
