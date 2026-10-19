import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Product

from .conftest import NOT_FOUND

spec = pytest.mark.spec
GTIN = "0051000198808"
Maker = async_sessionmaker[AsyncSession]
BROTH = {1008: 4.0, 2000: 0.43, 1258: 0.0, 1093: 353.0, 1004: 0.0, 1079: 0.0, 1003: 0.85}
HIT = {
    "fdcId": 2773769, "description": "Swanson Beef Broth", "gtinUpc": "00051000198808",
    "brandOwner": "CAMPBELL SOUP COMPANY", "brandName": "SWANSON",
    "ingredients": "BEEF STOCK, SALT", "brandedFoodCategory": "Canned Soup",
    "publishedDate": "2026-07-23",
    "foodNutrients": [{"nutrientId": k, "value": v} for k, v in BROTH.items()],
}  # fmt: skip


@pytest.fixture
def off_misses(off_mock: respx.MockRouter) -> None:
    off_mock.get(path__startswith="/api/v2/product/").respond(404, json=NOT_FOUND)


@spec("USDA-7", "USDA-8")
@pytest.mark.usefixtures("off_misses")
async def test_a_barcode_only_usda_has_is_stored_scored_and_credited(
    client: httpx.AsyncClient, usda_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    usda_mock.routes["search"].respond(200, json={"foods": [HIT]})
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Swanson Beef Broth" and body["brand"] == "SWANSON"
    assert body["score"]["status"] == "scored"
    assert body["attribution"] == "Nutrition data from USDA FoodData Central"
    assert usda_mock.routes["search"].calls.last.request.url.params["query"] == "00051000198808"
    async with sessionmaker() as s:
        product = await s.get(Product, GTIN)
        assert product is not None
        # Everything is from USDA except the additive list, derived from its ingredients (EST-5).
        sources = product.source_by_field
        assert sources["additives"] == "derived"
        assert {v for k, v in sources.items() if k != "additives"} == {"usda"}
        assert product.additives_known is True


@spec("USDA-9")
@pytest.mark.usefixtures("off_misses")
@pytest.mark.parametrize("usda_status", [200, 429, 503])
async def test_not_in_usda_or_usda_failing_is_still_a_404(
    client: httpx.AsyncClient, usda_mock: respx.MockRouter, usda_status: int
) -> None:
    usda_mock.routes["search"].respond(usda_status, json={"foods": []})
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 404 and r.json()["next"] == "contribute"


@spec("USDA-8")
async def test_off_products_still_credit_only_off(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, usda_mock: respx.MockRouter
) -> None:
    from .conftest import off_product

    off_mock.get("/api/v2/product/0036000291452.json").respond(200, json=off_product())
    body = (await client.get("/products/0036000291452")).json()
    assert body["attribution"] == "Data from Open Food Facts (ODbL)"
    assert not usda_mock.routes["search"].called


@spec("EST-5")
@pytest.mark.usefixtures("off_misses")
async def test_usda_products_get_additives_from_their_ingredient_list(
    client: httpx.AsyncClient, usda_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    ham = {**HIT, "ingredients": "PORK, WATER, SALT, SODIUM NITRITE."}
    usda_mock.routes["search"].respond(200, json={"foods": [ham]})
    body = (await client.get(f"/products/{GTIN}")).json()
    assert [a["code"] for a in body["additives"]] == ["e250"]
    assert body["score"]["components"]["additives"]["known"] is True
    async with sessionmaker() as s:
        product = await s.get(Product, GTIN)
        assert product is not None and product.source_by_field["additives"] == "derived"
