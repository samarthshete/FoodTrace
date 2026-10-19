from datetime import timedelta

import httpx
import pytest
import respx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Product, ProductAdditive, Score
from app.scoring.config import default_config

from .conftest import NOT_FOUND, NOW, USER_AGENT, off_product

spec = pytest.mark.spec
GTIN = "0036000291452"
UPC = "036000291452"
VERSION = default_config().engine_version
Maker = async_sessionmaker[AsyncSession]


def route13(mock: respx.MockRouter) -> respx.Route:
    return mock.get(f"/api/v2/product/{GTIN}.json")


def route12(mock: respx.MockRouter) -> respx.Route:
    return mock.get(f"/api/v2/product/{UPC}.json")


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    delays: list[float] = []

    async def fake_sleep(s: float) -> None:
        delays.append(s)

    monkeypatch.setattr("app.services.off_client.asyncio.sleep", fake_sleep)
    return delays


@spec("LOOKUP-1")
async def test_invalid_barcode_is_422_problem(client: httpx.AsyncClient) -> None:
    r = await client.get("/products/036000291453")
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "check digit" in r.json()["detail"]


@spec("LOOKUP-3", "LOOKUP-6", "LOOKUP-10")
async def test_live_hit_on_upc_form_is_stored_and_scored(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    route13(off_mock).respond(404, json=NOT_FOUND)
    route12(off_mock).respond(200, json=off_product())
    r = await client.get(f"/products/{UPC}")
    assert r.status_code == 200
    body = r.json()
    assert (
        body["gtin"] == GTIN
        and body["name"] == "Crunchy Oat Bars"
        and body["brand"] == "Acme Foods"
    )
    assert body["attribution"] == "Data from Open Food Facts (ODbL)"
    assert body["score"]["status"] == "scored" and "breakdown" not in body["score"]
    assert body["stale"] is False

    async with sessionmaker() as s:
        product = await s.get(Product, GTIN)
        assert product is not None and product.source_by_field["name"] == "off"
        codes = set(await s.scalars(select(ProductAdditive.additive_code)))
        assert codes == {"e250", "e330"}
        assert await s.get(Score, (GTIN, VERSION)) is not None


@spec("LOOKUP-2")
async def test_fresh_cache_hit_makes_no_outbound_call(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    live = route13(off_mock).respond(200, json=off_product())
    assert (await client.get(f"/products/{GTIN}")).status_code == 200
    assert live.call_count == 1
    assert (await client.get(f"/products/{GTIN}")).status_code == 200
    assert live.call_count == 1


@spec("LOOKUP-2", "LOOKUP-3")
async def test_stale_row_is_refreshed(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    live = route13(off_mock).respond(200, json=off_product())
    await client.get(f"/products/{GTIN}")
    async with sessionmaker() as s:
        await s.execute(text("UPDATE products SET fetched_at = :t"),
                        {"t": NOW - timedelta(days=31)})  # fmt: skip
        await s.commit()
    await client.get(f"/products/{GTIN}")
    assert live.call_count == 2


@spec("LOOKUP-4")
async def test_user_agent_is_descriptive(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    live = route13(off_mock).respond(200, json=off_product())
    await client.get(f"/products/{GTIN}")
    assert live.calls.last.request.headers["user-agent"] == USER_AGENT


@spec("LOOKUP-5")
async def test_backs_off_on_429_then_succeeds(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, no_sleep: list[float]
) -> None:
    route13(off_mock).side_effect = [
        httpx.Response(429, headers={"Retry-After": "2"}),
        httpx.Response(503),
        httpx.Response(200, json=off_product()),
    ]
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 200
    assert no_sleep == [2.0, 1.0]  # Retry-After honoured, then exponential


@spec("LOOKUP-5", "LOOKUP-8")
async def test_gives_up_after_retries_and_returns_503_without_row(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, no_sleep: list[float]
) -> None:
    live = route13(off_mock).respond(429, headers={"Retry-After": "60"})
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/problem+json")
    assert live.call_count == 3
    assert no_sleep == [5.0, 5.0]  # Retry-After capped at 5 s


@spec("LOOKUP-8")
async def test_stale_row_served_when_off_is_down(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker,
    no_sleep: list[float],
) -> None:  # fmt: skip
    route13(off_mock).side_effect = [httpx.Response(200, json=off_product())] + [
        httpx.Response(503)
    ] * 3
    await client.get(f"/products/{GTIN}")
    async with sessionmaker() as s:
        await s.execute(text("UPDATE products SET fetched_at = :t"),
                        {"t": NOW - timedelta(days=40)})  # fmt: skip
        await s.commit()
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 200 and r.json()["stale"] is True


@spec("LOOKUP-7")
async def test_not_found_points_to_contribute(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    route13(off_mock).respond(404, json=NOT_FOUND)
    route12(off_mock).respond(200, json=NOT_FOUND)
    r = await client.get(f"/products/{GTIN}")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["next"] == "contribute"


@spec("LOOKUP-9")
async def test_score_rows_are_per_version_and_not_rewritten(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    route13(off_mock).respond(200, json=off_product())
    await client.get(f"/products/{GTIN}")
    async with sessionmaker() as s:
        await s.execute(text(
            "INSERT INTO scores (gtin, engine_version, total, breakdown) "
            "VALUES (:g, '0.0.1-old', 12, '{}')"
        ), {"g": GTIN})  # fmt: skip
        await s.execute(text("UPDATE products SET fetched_at = :t"),
                        {"t": NOW - timedelta(days=31)})  # fmt: skip
        await s.commit()
    await client.get(f"/products/{GTIN}")  # refresh recomputes the current version only
    async with sessionmaker() as s:
        rows = (await s.execute(select(Score.engine_version, Score.total))).all()
    versions = dict(rows)
    assert versions["0.0.1-old"] == 12
    assert VERSION in versions


@spec("LOOKUP-11")
async def test_etag_and_conditional_get(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    route13(off_mock).respond(200, json=off_product())
    first = await client.get(f"/products/{GTIN}")
    etag = first.headers["etag"]
    assert first.headers["cache-control"] == "public, max-age=300"
    second = await client.get(f"/products/{GTIN}", headers={"If-None-Match": etag})
    assert second.status_code == 304 and second.content == b""


@spec("LOOKUP-12", "ADD-5")
async def test_breakdown_has_lines_explanation_and_cap(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    route13(off_mock).respond(200, json=off_product())
    r = await client.get(f"/products/{GTIN}/breakdown")
    assert r.status_code == 200
    body = r.json()
    rule_ids = [ln["rule_id"] for ln in body["score"]["breakdown"]]
    assert "nutriscore.general.sugars" in rule_ids and "additives.e250" in rule_ids
    assert "additives.cap" in rule_ids  # e250 is high risk + grade A in the fixture
    assert body["score"]["total"] <= 49
    assert body["explanation"][0].startswith("Scores ")


@spec("LOOKUP-12")
async def test_breakdown_unknown_product_is_404(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    route13(off_mock).respond(404, json=NOT_FOUND)
    route12(off_mock).respond(404, json=NOT_FOUND)
    r = await client.get(f"/products/{GTIN}/breakdown")
    assert r.status_code == 404 and r.json()["next"] == "contribute"


@spec("ENGINE-3", "LOOKUP-13")
async def test_product_without_salt_is_not_scored(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    payload = off_product()
    del payload["product"]["nutriments"]["salt_100g"]
    payload["product"]["nutriments"]["sugars_100g"] = "n/a"
    route13(off_mock).respond(200, json=payload)
    body = (await client.get(f"/products/{GTIN}")).json()
    assert body["score"]["status"] == "not_scored" and body["score"]["total"] is None
    assert {"salt_g", "sugars_g"} <= set(body["score"]["missing_inputs"])


@spec("FDA-5")
async def test_product_lists_its_additives_with_us_status(
    client: httpx.AsyncClient, off_mock: respx.MockRouter, sessionmaker: Maker
) -> None:
    async with sessionmaker() as s:
        await s.execute(text(
            "UPDATE additives SET us_status = 'food_additive', fda_cfr_ref = '172.170' "
            "WHERE code = 'e250'"
        ))  # fmt: skip
        await s.commit()
    route13(off_mock).respond(200, json=off_product())
    body = (await client.get(f"/products/{GTIN}")).json()
    assert body["additives"] == [
        {"code": "e250", "name": "E250 - Sodium nitrite", "us_status": "food_additive",
         "fda_cfr_ref": "172.170"},
        {"code": "e330", "name": "E330 - Citric acid", "us_status": None, "fda_cfr_ref": None},
    ]  # fmt: skip


@spec("ACC-6")
async def test_product_carries_allergens_and_says_whether_they_are_known(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    route13(off_mock).respond(200, json=off_product(
        allergens_tags=["en:gluten"], traces_tags=["en:nuts"],
        ingredients_analysis_tags=["en:vegan"],
    ))  # fmt: skip
    body = (await client.get(f"/products/{GTIN}")).json()
    assert body["allergens"] == ["en:gluten"] and body["traces"] == ["en:nuts"]
    assert body["ingredients_analysis"] == ["en:vegan"] and body["allergens_known"] is True
