from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Product, Score
from app.scoring.config import default_config

from .conftest import NOT_FOUND, NOW, off_product

spec = pytest.mark.spec
GTIN = "0036000291452"  # the base product: 41/100, general class, primary en:cereal-bars
VERSION = default_config().engine_version
CATS = ["en:foods", "en:snacks", "en:sweet-snacks", "en:cereal-bars"]
Maker = async_sessionmaker[AsyncSession]

# Valid GTIN-13s for the candidates (check digits computed per spec 001).
CANDIDATES = ["0000000000017", "0000000000024", "0000000000031", "0000000000048",
              "0000000000055", "0000000000062", "0000000000079"]  # fmt: skip


async def add_scored(
    maker: Maker,
    gtin: str,
    total: int | None,
    *,
    categories: list[str] | None = None,
    confidence: float = 1.0,
    nutri_class: str = "general",
) -> None:
    """Insert a product and a current-version score row without going through OFF."""
    cats = categories if categories is not None else ["en:snacks", "en:cereal-bars"]
    status = "scored" if total is not None else "not_scored"
    band: dict[str, Any] | None = {"id": "good", "label": "Good"} if total is not None else None
    async with maker() as s:
        image = f"https://img.test/{gtin}.jpg"
        s.add(Product(gtin=gtin, name=f"Bar {gtin[-2:]}", brand="Other", primary_category=cats[-1],
                      categories=cats, image_url=image, fetched_at=NOW))  # fmt: skip
        await s.flush()
        s.add(Score(gtin=gtin, engine_version=VERSION, total=total, breakdown={
            "status": status, "total": total, "band": band, "confidence": confidence,
            "nutriscore": {"class": nutri_class},
        }))  # fmt: skip
        await s.commit()


@pytest.fixture
async def base(off_mock: respx.MockRouter, client: httpx.AsyncClient) -> None:
    off_mock.get(f"/api/v2/product/{GTIN}.json").respond(
        200, json=off_product(categories_tags=CATS)
    )
    r = await client.get(f"/products/{GTIN}")
    assert r.json()["score"]["total"] == 41


async def alternatives(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.get(f"/products/{GTIN}/alternatives")
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def gtins(body: dict[str, Any]) -> list[str]:
    return [a["gtin"] for a in body["alternatives"]]


@spec("ALT-1")
async def test_invalid_and_unknown_products_give_the_lookup_errors(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    assert (await client.get("/products/036000291453/alternatives")).status_code == 422
    off_mock.get(path__startswith="/api/v2/product/").respond(404, json=NOT_FOUND)
    r = await client.get(f"/products/{GTIN}/alternatives")
    assert r.status_code == 404 and r.json()["next"] == "contribute"


@spec("ALT-2", "ALT-3")
@pytest.mark.usefixtures("base")
async def test_only_confident_scored_products_of_the_same_class(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    ok, unscored, limited, drink = CANDIDATES[:4]
    await add_scored(sessionmaker, ok, 80)
    await add_scored(sessionmaker, unscored, None)
    await add_scored(sessionmaker, limited, 90, confidence=0.5)
    await add_scored(sessionmaker, drink, 95, nutri_class="beverage")
    assert gtins(await alternatives(client)) == [ok]


@spec("ALT-4")
@pytest.mark.usefixtures("base")
async def test_falls_back_to_less_specific_categories_but_not_too_far(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    snack, food = CANDIDATES[:2]
    await add_scored(sessionmaker, snack, 70, categories=["en:snacks", "en:sweet-snacks"])
    await add_scored(sessionmaker, food, 99, categories=["en:foods"])
    body = await alternatives(client)
    assert body["category"] == "en:sweet-snacks" and gtins(body) == [snack]


@spec("ALT-4")
@pytest.mark.usefixtures("base")
async def test_primary_category_wins_over_better_scores_in_broader_ones(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    bar, snack = CANDIDATES[:2]
    await add_scored(sessionmaker, bar, 60)
    await add_scored(sessionmaker, snack, 99, categories=["en:snacks", "en:sweet-snacks"])
    body = await alternatives(client)
    assert body["category"] == "en:cereal-bars" and gtins(body) == [bar]


@spec("ALT-5")
@pytest.mark.usefixtures("base")
async def test_must_beat_the_base_score_by_min_gain(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    just_under, just_enough = CANDIDATES[:2]
    await add_scored(sessionmaker, just_under, 45)  # 41 + 4
    await add_scored(sessionmaker, just_enough, 46)  # 41 + 5
    assert gtins(await alternatives(client)) == [just_enough]


@spec("ALT-5")
async def test_unscored_base_shows_the_best_in_category(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    product = off_product(categories_tags=CATS)
    del product["product"]["nutriments"]["sugars_100g"]  # required input missing → not scored
    off_mock.get(f"/api/v2/product/{GTIN}.json").respond(200, json=product)
    assert (await client.get(f"/products/{GTIN}")).json()["score"]["status"] == "not_scored"
    await add_scored(sessionmaker, CANDIDATES[0], 30)
    assert gtins(await alternatives(client)) == [CANDIDATES[0]]


@spec("ALT-6", "ALT-7")
@pytest.mark.usefixtures("base")
async def test_top_five_ordered_with_display_fields(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    totals = [60, 90, 75, 75, 99, 55, 80]
    for gtin, total in zip(CANDIDATES, totals, strict=True):
        await add_scored(sessionmaker, gtin, total, confidence=0.9 if gtin.endswith("31") else 1.0)
    body = await alternatives(client)
    # 99, 90, 80, then the two 75s by confidence (…48 has 1.0, …31 has 0.9). 60 and 55 drop off.
    assert gtins(body) == [CANDIDATES[4], CANDIDATES[1], CANDIDATES[6], CANDIDATES[3],
                           CANDIDATES[2]]  # fmt: skip
    assert GTIN not in gtins(body)
    first = body["alternatives"][0]
    assert first == {
        "gtin": CANDIDATES[4], "name": "Bar 55", "brand": "Other",
        "image_url": f"https://img.test/{CANDIDATES[4]}.jpg", "total": 99,
        "band": {"id": "good", "label": "Good"}, "confidence": 1.0,
    }  # fmt: skip
    assert body["gtin"] == GTIN and body["attribution"] == "Data from Open Food Facts (ODbL)"


@spec("ALT-8", "ALT-9")
@pytest.mark.usefixtures("base")
async def test_no_candidates_is_an_empty_list_with_cache_headers(
    client: httpx.AsyncClient,
) -> None:
    r = await client.get(f"/products/{GTIN}/alternatives")
    assert r.status_code == 200
    assert r.json()["alternatives"] == [] and r.json()["category"] is None
    assert r.headers["cache-control"] == "public, max-age=300"
    assert "etag" not in r.headers
