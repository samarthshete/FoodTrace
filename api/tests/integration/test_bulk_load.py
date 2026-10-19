from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Product, ProductAdditive, Score
from app.scoring.config import default_config
from pipeline.load import DatabaseTooLarge, Item, load_products
from pipeline.off_bulk import mapped_rows

from ..pipeline.export_rows import export_row, write_extract
from .conftest import NOW

spec = pytest.mark.spec
Maker = async_sessionmaker[AsyncSession]
VERSION = default_config().engine_version
A, B = "0000000000017", "0000000000024"


def items(tmp_path: Path, *rows: dict[str, Any], now: datetime = NOW) -> list[Item]:
    return mapped_rows(write_extract(tmp_path, list(rows)), now)


async def count(maker: Maker, model: Any) -> int:
    async with maker() as s:
        return int(await s.scalar(select(func.count()).select_from(model)) or 0)


@spec("OFF-6", "OFF-7", "OFF-8", "OFF-11")
async def test_load_writes_links_and_scores_then_is_idempotent(
    tmp_path: Path, sessionmaker: Maker, migrated_db: str
) -> None:
    batch = items(tmp_path, export_row(A), export_row(B, additives_tags="en:e999z"))
    first = await load_products(migrated_db, batch, NOW)
    assert (first.offered, first.written, first.kept_newer, first.scored) == (2, 2, 0, 2)
    assert "2 products offered, 2 written" in str(first)
    async with sessionmaker() as s:
        links = set(await s.execute(select(ProductAdditive.gtin, ProductAdditive.additive_code)))
        assert links == {(A, "e330"), (B, "e999z")}  # e999z got a stub additive row
        score = await s.get(Score, (A, VERSION))
        assert score is not None and score.total is not None
        assert "breakdown" not in score.breakdown  # compact bulk row

    second = await load_products(migrated_db, batch, NOW + timedelta(hours=1))
    assert (second.written, second.kept_newer, second.scored) == (0, 2, 0)


@spec("OFF-6")
async def test_a_newer_live_row_is_kept_and_live_only_rows_survive(
    tmp_path: Path, sessionmaker: Maker, migrated_db: str
) -> None:
    edited = int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())
    async with sessionmaker() as s:
        s.add(
            Product(gtin=A, name="Live name", categories=[], fetched_at=NOW)
        )  # fetched after edit
        s.add(
            Product(
                gtin=B,
                name="Old live name",
                categories=[],
                fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )  # fetched before edit
        s.add(Product(gtin="0000000000031", name="Live only", categories=[], fetched_at=NOW))
        await s.commit()
    batch = items(tmp_path, export_row(A, last_modified_t=str(edited)),
                  export_row(B, last_modified_t=str(edited)))  # fmt: skip
    report = await load_products(migrated_db, batch, NOW)
    assert (report.written, report.kept_newer) == (1, 1)
    async with sessionmaker() as s:
        names = {g: n for g, n in await s.execute(select(Product.gtin, Product.name))}
    assert names == {A: "Live name", B: "Oat Bars", "0000000000031": "Live only"}


@spec("OFF-8")
async def test_kept_rows_without_a_current_score_are_scored(
    tmp_path: Path, sessionmaker: Maker, migrated_db: str
) -> None:
    batch = items(tmp_path, export_row(A))
    await load_products(migrated_db, batch, NOW)
    async with sessionmaker() as s:
        await s.execute(text("DELETE FROM scores"))  # as after an engine_version bump
        await s.commit()
    report = await load_products(migrated_db, batch, NOW + timedelta(hours=1))
    assert (report.written, report.scored) == (0, 1)


@spec("OFF-8")
async def test_viewing_a_bulk_product_fills_in_its_breakdown_with_the_same_score(
    tmp_path: Path, sessionmaker: Maker, migrated_db: str, client: Any
) -> None:
    await load_products(migrated_db, items(tmp_path, export_row(A)), NOW)
    async with sessionmaker() as s:
        compact = await s.get(Score, (A, VERSION))
        assert compact is not None
        total = compact.total
    r = await client.get(f"/products/{A}/breakdown")
    assert r.status_code == 200 and r.json()["score"]["total"] == total
    async with sessionmaker() as s:
        full = await s.get(Score, (A, VERSION))
        assert full is not None and "breakdown" in full.breakdown and full.total == total


@spec("OFF-9")
async def test_a_load_over_the_size_budget_changes_nothing(
    tmp_path: Path, sessionmaker: Maker, migrated_db: str
) -> None:
    with pytest.raises(DatabaseTooLarge):
        await load_products(migrated_db, items(tmp_path, export_row(A)), NOW, max_mb=0.001)
    assert await count(sessionmaker, Product) == 0
    assert await count(sessionmaker, Score) == 0
