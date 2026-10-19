"""Golden gate: does our Nutri-Score grade match Open Food Facts' own? (specs/015)

Usage: uv run python -m pipeline.golden [--min-match 0.99] [--sample N]

Reads the US extract (data/off/us.parquet, from pipeline.off_bulk), which carries OFF's
`nutriscore_grade`. Products are mapped exactly as the import maps them, then graded by our
Nutri-Score port. Mismatches go to reports/golden_mismatches.csv. Exits non-zero below the
threshold.
"""

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from app.scoring import nutriscore_2023
from app.scoring.config import ScoringConfig, default_config
from app.scoring.engine import _with_estimates
from app.services.lookup import build_facts
from app.services.off_mapping import additive_codes, map_product
from pipeline.off_bulk import EXTRACT, to_api_product

REPORT = Path("reports/golden_mismatches.csv")
FULL = ("energy_kj", "sugars_g", "saturated_fat_g", "salt_g", "fiber_g", "proteins_g")  # GOLD-1
MIN_PRODUCTS = 2000


@dataclass(frozen=True)
class Graded:
    code: str
    name: str | None
    nutri_class: str
    ours: str
    ours_score: int | None
    theirs: str
    theirs_score: int | None


def grade_rows(rows: list[dict[str, Any]], cfg: ScoringConfig) -> list[Graded]:
    """Grade every product with a full nutrition panel and an OFF grade (GOLD-1, GOLD-2)."""
    now = datetime.now(UTC)
    out = []
    for row in rows:
        if row["nutriscore_grade"] not in ("a", "b", "c", "d", "e"):
            continue
        product = to_api_product(row)
        mapped = map_product("0000000000000", product, now)
        if not all(k in mapped["nutrition"] for k in FULL):
            continue
        facts = build_facts(mapped["nutrition"], mapped["categories"], mapped["nova_group"],
                            None, mapped["ingredients_text"])  # fmt: skip
        facts, _ = _with_estimates(facts, cfg)
        ns = nutriscore_2023.compute(facts, cfg.nutriscore, additive_codes(product) or [])
        if ns.grade is None:
            continue
        out.append(Graded(row["code"], row["product_name"], ns.nutri_class, ns.grade, ns.score,
                          row["nutriscore_grade"], row["nutriscore_score"]))  # fmt: skip
    return out


def summarize(graded: list[Graded]) -> tuple[float, Counter[tuple[str, bool]]]:
    by_class: Counter[tuple[str, bool]] = Counter(
        (g.nutri_class, g.ours == g.theirs) for g in graded
    )
    matched = sum(1 for g in graded if g.ours == g.theirs)
    return (matched / len(graded) if graded else 0.0), by_class


def write_mismatches(graded: list[Graded], path: Path = REPORT) -> int:  # GOLD-3
    path.parent.mkdir(parents=True, exist_ok=True)
    misses = [g for g in graded if g.ours != g.theirs]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "class", "our_grade", "our_score", "off_grade", "off_score"])
        for g in misses:
            w.writerow([g.code, g.name, g.nutri_class, g.ours, g.ours_score, g.theirs,
                        g.theirs_score])  # fmt: skip
    return len(misses)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-match", type=float, default=0.99)
    parser.add_argument("--sample", type=int, help="grade a random sample of N rows")
    args = parser.parse_args()
    df = pl.read_parquet(EXTRACT)
    if args.sample:
        df = df.sample(n=min(args.sample, df.height), seed=42)
    graded = grade_rows(list(df.iter_rows(named=True)), default_config())
    rate, by_class = summarize(graded)
    misses = write_mismatches(graded)
    print(f"golden: {len(graded)} products, {rate:.2%} match OFF's grade, "
          f"{misses} mismatches in {REPORT}")  # fmt: skip
    for cls in sorted({c for c, _ in by_class}):
        ok, bad = by_class[(cls, True)], by_class[(cls, False)]
        print(f"  {cls}: {ok}/{ok + bad}")
    if len(graded) < MIN_PRODUCTS or rate < args.min_match:  # GOLD-4
        sys.exit(f"golden gate failed: need >= {MIN_PRODUCTS} products at >= {args.min_match:.0%}")


if __name__ == "__main__":
    main()
