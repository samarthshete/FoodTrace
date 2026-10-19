from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Recall, RecallSync
from pipeline.recalls import rows_in_window, sync

from .conftest import NOT_FOUND, NOW, off_product

spec = pytest.mark.spec
GTIN = "0036000291452"  # Crunchy Oat Bars by Acme Foods (conftest)
Maker = async_sessionmaker[AsyncSession]


def record(
    number: str, description: str, *, started: str = "20260801", **kw: Any
) -> dict[str, Any]:
    return {
        "recall_number": number, "status": "Ongoing", "classification": "Class II",
        "recalling_firm": kw.get("firm", "Other Firm"), "product_description": description,
        "code_info": kw.get("code_info", ""), "reason_for_recall": f"Reason {number}",
        "recall_initiation_date": started, "report_date": kw.get("reported", "20260901"),
    }  # fmt: skip


@pytest.fixture
async def recalls(sessionmaker: Maker) -> AsyncIterator[Maker]:
    async with sessionmaker() as s:
        await s.execute(text("TRUNCATE recalls, recall_sync"))
        await s.commit()
    yield sessionmaker


async def load(maker: Maker, records: list[dict[str, Any]]) -> None:
    async with maker() as s:
        await sync(s, rows_in_window(records, NOW.date(), 3), NOW)


@pytest.fixture
async def base(off_mock: respx.MockRouter, client: httpx.AsyncClient) -> None:
    off_mock.get(f"/api/v2/product/{GTIN}.json").respond(200, json=off_product())
    assert (await client.get(f"/products/{GTIN}")).status_code == 200


async def get(client: httpx.AsyncClient) -> httpx.Response:
    r = await client.get(f"/products/{GTIN}/recalls")
    assert r.status_code == 200, r.text
    return r


@spec("RECALL-2", "RECALL-4")
async def test_sync_mirrors_the_window_and_is_idempotent(recalls: Maker) -> None:
    batch = [record("A", "x"), record("B", "y"), record("OLD", "z", reported="20200101")]
    await load(recalls, batch)
    await load(recalls, batch)
    async with recalls() as s:
        assert sorted(await s.scalars(select(Recall.recall_number))) == ["A", "B"]
        sync_row = await s.get(RecallSync, "openfda")
        assert sync_row is not None and sync_row.as_of == NOW
    await load(recalls, [record("A", "x changed")])  # B dropped out of the file
    async with recalls() as s:
        assert await s.scalar(select(func.count()).select_from(Recall)) == 1
        a = await s.get(Recall, "A")
        assert a is not None and a.product_description == "x changed"


@spec("RECALL-8")
async def test_errors_match_the_product_lookup(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, recalls: Maker
) -> None:
    assert (await client.get("/products/036000291453/recalls")).status_code == 422
    off_mock.get(path__startswith="/api/v2/product/").respond(404, json=NOT_FOUND)
    assert (await client.get(f"/products/{GTIN}/recalls")).status_code == 404


@spec("RECALL-8", "RECALL-11")
@pytest.mark.usefixtures("base")
async def test_never_synced_gives_null_as_of_and_no_recalls(
    client: httpx.AsyncClient, recalls: Maker
) -> None:
    r = await get(client)
    assert r.json() == {
        "gtin": GTIN, "recalls": [], "as_of": None,
        "attribution": "Recall data from openFDA (FDA)",
    }  # fmt: skip
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert "etag" not in r.headers


@spec("RECALL-5", "RECALL-6", "RECALL-9", "RECALL-10")
@pytest.mark.usefixtures("base")
async def test_code_matches_first_then_newest_capped_at_three(
    client: httpx.AsyncClient, recalls: Maker
) -> None:
    by_name = "Acme Foods Crunchy Oat Bars, 6 ct"
    await load(recalls, [
        record("N1", by_name, started="20260101"),
        record("N2", by_name, started="20260601"),
        record("N3", by_name, started="20250601"),
        record("CODE", "Assorted bars", started="20240101", code_info="UPC 0 36000 29145 2"),
        record("MISS", "Acme Foods chocolate cookies"),
    ])  # fmt: skip
    body = (await get(client)).json()
    assert [r["recall_number"] for r in body["recalls"]] == ["CODE", "N2", "N1"]
    assert [r["match"] for r in body["recalls"]] == ["code", "brand_name", "brand_name"]
    assert body["as_of"] == NOW.isoformat()
    first = body["recalls"][0]
    assert first == {
        "recall_number": "CODE", "match": "code", "classification": "Class II",
        "status": "Ongoing", "reason_for_recall": "Reason CODE",
        "recall_initiation_date": "2024-01-01", "product_description": "Assorted bars",
        "url": "https://api.fda.gov/food/enforcement.json?search=recall_number:%22CODE%22",
    }  # fmt: skip


@spec("RECALL-2")
@pytest.mark.usefixtures("base")
async def test_records_outside_the_window_never_match(
    client: httpx.AsyncClient, recalls: Maker
) -> None:
    old = (NOW - timedelta(days=4 * 365)).strftime("%Y%m%d")
    await load(recalls, [record("OLD", "Acme Foods Crunchy Oat Bars", reported=old)])
    assert (await get(client)).json()["recalls"] == []
