from decimal import Decimal
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
BAND = {"id": "good", "label": "Good"}


async def add(
    maker: Maker, gtin: str, name: str | None, category: str, total: int | None, *,
    image: bool = True, completeness: str = "0.80", grade: str | None = "b",
    version: str = VERSION,
) -> None:  # fmt: skip
    async with maker() as s:
        s.add(Product(gtin=gtin, name=name, brand="Brand", primary_category=category,
                      categories=[category], fetched_at=NOW, nova_group=3,
                      completeness=Decimal(completeness),
                      image_url=f"https://img.test/{gtin}.jpg" if image else None))  # fmt: skip
        await s.flush()
        scored = total is not None
        breakdown: dict[str, Any] = {
            "status": "scored" if scored else "not_scored",
            "total": total,
            "band": BAND if scored else None,
        }
        if grade:
            breakdown["nutriscore"] = {"class": "general", "score": 2, "grade": grade}
        s.add(Score(gtin=gtin, engine_version=version, total=total, breakdown=breakdown))
        await s.commit()


@pytest.fixture
async def shelf(sessionmaker: Maker) -> None:
    await add(sessionmaker, "0000000000017", "Bran Flakes", "en:breakfast-cereals", 80)
    await add(sessionmaker, "0000000000024", "Oats", "en:rolled-oats", 90, grade=None)
    await add(sessionmaker, "0000000000031", "No Photo Muesli", "en:mueslis", 99, image=False)
    await add(sessionmaker, "0000000000048", "Granola", "en:breakfast-cereals", 80,
              completeness="0.95")  # fmt: skip
    await add(sessionmaker, "0000000000055", "Unscored Flakes", "en:breakfast-cereals", None)
    await add(sessionmaker, "0000000000062", "  ", "en:breakfast-cereals", 95)
    await add(sessionmaker, "0000000000079", "Old Engine Cereal", "en:breakfast-cereals", 97,
              version="0.0.1")  # fmt: skip
    await add(sessionmaker, "0000000000086", "Cheddar", "en:cheeses", 40, grade="d")
    await add(sessionmaker, "0000000000093", "Socks", "en:clothing", 99)


@spec("EXPLORE-1", "EXPLORE-2", "EXPLORE-4")
@pytest.mark.usefixtures("shelf")
async def test_every_group_in_order_with_its_top_products(client: httpx.AsyncClient) -> None:
    r = await client.get("/explore")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=600"
    body = r.json()
    assert body["engine_version"] == VERSION
    cats = body["categories"]
    assert [c["id"] for c in cats][:2] == ["breakfast", "yogurts"] and len(cats) == 10
    cheese = next(c for c in cats if c["id"] == "cheese")
    assert cheese["label"] == "Cheese" and cheese["blurb"]
    assert cheese["products"] == [{
        "gtin": "0000000000086", "name": "Cheddar", "brand": "Brand",
        "image_url": "https://img.test/0000000000086.jpg", "total": 40, "band": BAND,
        "nutriscore_grade": "d", "nova_group": 3,
    }]  # fmt: skip
    assert next(c for c in cats if c["id"] == "yogurts")["products"] == []
    assert "Socks" not in r.text


@spec("EXPLORE-3")
@pytest.mark.usefixtures("shelf")
async def test_scored_named_current_products_image_first_then_score(
    client: httpx.AsyncClient,
) -> None:
    cats = (await client.get("/explore")).json()["categories"]
    breakfast = next(c for c in cats if c["id"] == "breakfast")["products"]
    assert [p["name"] for p in breakfast] == ["Oats", "Granola", "Bran Flakes", "No Photo Muesli"]
    assert breakfast[0]["nutriscore_grade"] is None


@spec("EXPLORE-2")
@pytest.mark.usefixtures("shelf")
async def test_per_category_limits_each_group(client: httpx.AsyncClient) -> None:
    cats = (await client.get("/explore", params={"per_category": 2})).json()["categories"]
    assert [p["name"] for p in cats[0]["products"]] == ["Oats", "Granola"]


@spec("EXPLORE-5")
@pytest.mark.usefixtures("shelf")
async def test_one_group_and_unknown_ids(client: httpx.AsyncClient) -> None:
    r = await client.get("/explore/breakfast", params={"limit": 3})
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=600"
    body = r.json()
    assert (body["id"], body["label"]) == ("breakfast", "Breakfast cereals")
    assert [p["name"] for p in body["products"]] == ["Oats", "Granola", "Bran Flakes"]
    missing = await client.get("/explore/clothing")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
