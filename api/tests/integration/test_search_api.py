from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Product, Score
from app.scoring.config import default_config

from .conftest import NOW

spec = pytest.mark.spec
Maker = async_sessionmaker[AsyncSession]
VERSION = default_config().engine_version


async def add(maker: Maker, gtin: str, name: str, brand: str, total: int | None = None) -> None:
    async with maker() as s:
        s.add(Product(gtin=gtin, name=name, brand=brand, categories=[], fetched_at=NOW,
                      image_url=f"https://img.test/{gtin}.jpg"))  # fmt: skip
        await s.flush()
        if total is not None:
            band = {"id": "good", "label": "Good"}
            s.add(Score(gtin=gtin, engine_version=VERSION, total=total,
                        breakdown={"status": "scored", "total": total, "band": band}))  # fmt: skip
        await s.commit()


@pytest.fixture
async def catalog(sessionmaker: Maker) -> None:
    await add(sessionmaker, "0000000000017", "Honey Nut Cheerios", "General Mills", 55)
    await add(sessionmaker, "0000000000024", "Cheerios", "General Mills", 70)
    await add(sessionmaker, "0000000000031", "Oat Milk", "Oatly")
    await add(sessionmaker, "0000000000048", "Peanut Butter", "Jif", 40)


async def search(client: httpx.AsyncClient, **params: Any) -> httpx.Response:
    return await client.get("/search", params=params)


@spec("SEARCH-1")
@pytest.mark.parametrize("q", ["", " a ", "x" * 101])
async def test_queries_must_be_2_to_100_characters(client: httpx.AsyncClient, q: str) -> None:
    r = await search(client, q=q)
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")


@spec("SEARCH-2", "SEARCH-4", "SEARCH-6")
@pytest.mark.usefixtures("catalog")
async def test_prefix_words_match_name_or_brand_best_first(client: httpx.AsyncClient) -> None:
    r = await search(client, q="cheer")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=300"
    results = r.json()["results"]
    assert [x["name"] for x in results] == ["Cheerios", "Honey Nut Cheerios"]
    assert results[0] == {"gtin": "0000000000024", "name": "Cheerios", "brand": "General Mills",
                          "image_url": "https://img.test/0000000000024.jpg", "total": 70,
                          "band": {"id": "good", "label": "Good"}}  # fmt: skip
    by_brand = (await search(client, q="general mills honey")).json()["results"]
    assert [x["name"] for x in by_brand] == ["Honey Nut Cheerios"]


@spec("SEARCH-2")
@pytest.mark.usefixtures("catalog")
async def test_typos_match_by_similarity(client: httpx.AsyncClient) -> None:
    results = (await search(client, q="peanut buter")).json()["results"]
    assert [x["name"] for x in results] == ["Peanut Butter"]


@spec("SEARCH-1", "SEARCH-4")
@pytest.mark.usefixtures("catalog")
async def test_limit_and_unscored_results(client: httpx.AsyncClient) -> None:
    assert len((await search(client, q="cheerios", limit=1)).json()["results"]) == 1
    [oat] = (await search(client, q="oat milk")).json()["results"]
    assert oat["total"] is None and oat["band"] is None


@spec("SEARCH-3", "SEARCH-5")
@pytest.mark.usefixtures("catalog")
async def test_barcodes_return_a_gtin_and_operators_are_harmless(client: httpx.AsyncClient) -> None:
    body = (await search(client, q="036000291452")).json()
    assert body["gtin"] == "0036000291452" and body["results"] == []
    assert (await search(client, q="'); drop table products; --")).status_code == 200
    assert (await search(client, q="!!")).json()["results"] == []
