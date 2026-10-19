from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Contribution, Product
from app.main import app
from app.routers.contributions import get_limiter
from app.services.contributions import RateLimiter
from app.settings import Settings, get_settings

from .conftest import OFF_BASE

spec = pytest.mark.spec
Maker = async_sessionmaker[AsyncSession]
GTIN = "0000000000017"
BODY: dict[str, Any] = {"gtin": "000000000017", "name": "Granola", "brand": "Acme", "kind": "food",
        "ingredients_text": "Oats, honey, sodium nitrite",
        "nutrition": {"energy_kj": 1750, "sugars_g": 21.8, "saturated_fat_g": 1.8,
                      "salt_g": 0.73, "fiber_g": 7.3, "proteins_g": 5.5}}  # fmt: skip


@pytest.fixture(autouse=True)
async def clean(sessionmaker: Maker) -> None:
    async with sessionmaker() as s:
        await s.execute(delete(Contribution))
        await s.commit()
    app.dependency_overrides[get_limiter] = lambda: RateLimiter(100)


def with_off_account() -> None:
    settings = Settings(off_base_url=OFF_BASE, off_user="bot", off_password="pw")
    app.dependency_overrides[get_settings] = lambda: settings


@spec("CONTRIB-4", "CONTRIB-6")
async def test_a_contribution_is_saved_scored_and_returned(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    r = await client.post("/contributions", json=BODY)
    assert r.status_code == 201, r.text
    product = r.json()
    assert product["gtin"] == GTIN and product["score"]["status"] == "scored"
    assert product["shared_with_off"] is None and r.headers["location"] == f"/products/{GTIN}"
    async with sessionmaker() as s:
        row = await s.get(Product, GTIN)
        assert row is not None and set(row.source_by_field.values()) == {"contribution"}
        [c] = (await s.scalars(select(Contribution))).all()
        assert c.status == "accepted" and c.user_id is None and c.extracted["name"] == "Granola"
    assert (await client.get(f"/products/{GTIN}")).json()["name"] == "Granola"


@spec("CONTRIB-5")
async def test_existing_products_are_never_overwritten(client: httpx.AsyncClient) -> None:
    assert (await client.post("/contributions", json=BODY)).status_code == 201
    r = await client.post("/contributions", json={**BODY, "name": "Other"})
    assert r.status_code == 409 and r.json()["gtin"] == GTIN


@spec("CONTRIB-4")
@pytest.mark.parametrize(
    ("change", "field"),
    [({"gtin": "000000000018"}, None), ({"kind": "pet food"}, "kind"),
     ({"nutrition": {**BODY["nutrition"], "salt_g": 200}}, "nutrition.salt_g")],
)  # fmt: skip
async def test_invalid_contributions_are_problems_naming_the_field(
    client: httpx.AsyncClient, change: dict[str, Any], field: str | None
) -> None:
    r = await client.post("/contributions", json={**BODY, **change})
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")
    if field:
        assert r.json()["detail"].startswith(field)


@spec("CONTRIB-8")
async def test_too_many_contributions_from_one_client_are_refused(
    client: httpx.AsyncClient,
) -> None:
    one_per_hour = RateLimiter(1)
    app.dependency_overrides[get_limiter] = lambda: one_per_hour
    assert (await client.post("/contributions", json=BODY)).status_code == 201
    other = {**BODY, "gtin": "0000000000024"}
    assert (await client.post("/contributions", json=other)).status_code == 429


@spec("CONTRIB-9")
async def test_sharing_is_offered_only_with_an_off_account(client: httpx.AsyncClient) -> None:
    assert (await client.get("/contributions/config")).json() == {"can_share_with_off": False}
    with_off_account()
    assert (await client.get("/contributions/config")).json() == {"can_share_with_off": True}


@spec("CONTRIB-10")
async def test_opted_in_contributions_are_sent_to_off_and_failures_dont_block(
    client: httpx.AsyncClient, off_mock: respx.MockRouter
) -> None:
    with_off_account()
    write = off_mock.post("/cgi/product_jqm2.pl").respond(200, json={"status": 1})
    r = await client.post("/contributions", json={**BODY, "share_with_off": True})
    assert r.status_code == 201 and r.json()["shared_with_off"] == "ok"
    sent = write.calls.last.request.content.decode()
    assert "code=0000000000017" in sent and "user_id=bot" in sent and "nutriment_salt=0.73" in sent

    off_mock.post("/cgi/product_jqm2.pl").respond(500)
    r = await client.post("/contributions", json={**BODY, "gtin": "0000000000024",
                                                  "share_with_off": True})  # fmt: skip
    assert r.status_code == 201 and r.json()["shared_with_off"].startswith("error")
