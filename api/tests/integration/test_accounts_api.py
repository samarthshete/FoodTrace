import time
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx
import jwt
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import JWKSCache
from app.main import app
from app.routers import me as me_router
from app.routers.products import get_now
from app.settings import Settings, get_settings

from ..auth_tokens import JWKS_URL, KID, WEB, jwks, token
from .conftest import NOW, off_product

spec = pytest.mark.spec
Maker = async_sessionmaker[AsyncSession]
GTIN, OTHER = "0036000291452", "0000000000017"
ALICE, BOB = "user-alice", "user-bob"


def auth(user: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(user)}"}


@pytest.fixture
async def accounts(
    sessionmaker: Maker, off_mock: respx.MockRouter, client: httpx.AsyncClient
) -> AsyncIterator[None]:
    """Two users, two products, and the web app's JWKS."""
    settings = Settings(auth_jwks_url=JWKS_URL, auth_issuer=WEB, auth_audience=WEB)
    app.dependency_overrides[get_settings] = lambda: settings
    async with sessionmaker() as s:
        await s.execute(text('TRUNCATE "user", contributions CASCADE'))
        for uid in (ALICE, BOB):
            await s.execute(text(
                'INSERT INTO "user" (id, name, email, "emailVerified", "createdAt", "updatedAt") '
                "VALUES (:id, :id, :id || '@example.com', true, now(), now())"
            ), {"id": uid})  # fmt: skip
        await s.commit()
    cache = JWKSCache()  # pre-loaded; fetching the JWKS is covered by the unit tests
    cache._keys = {KID: jwt.PyJWK(jwks()["keys"][0]).key}
    cache._fetched = time.monotonic()
    app.state.jwks = cache
    off_mock.get(f"/api/v2/product/{GTIN}.json").respond(200, json=off_product())
    off_mock.get(f"/api/v2/product/{OTHER}.json").respond(
        200, json=off_product(OTHER, product_name="Other Bars")
    )
    for g in (GTIN, OTHER):
        assert (await client.get(f"/products/{g}")).status_code == 200
    yield
    app.state.jwks = None


async def scan(client: httpx.AsyncClient, user: str, gtin: str = GTIN) -> httpx.Response:
    return await client.post("/me/history", json={"gtin": gtin}, headers=auth(user))


@spec("ACC-3")
@pytest.mark.usefixtures("accounts")
async def test_me_routes_need_a_valid_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/me")
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")
    expired = {"Authorization": f"Bearer {token(ALICE, ttl=-5)}"}
    assert (await client.get("/me/history", headers=expired)).status_code == 401
    assert (await client.get("/me", headers=auth(ALICE))).status_code == 200


@spec("ACC-5")
@pytest.mark.usefixtures("accounts")
async def test_profile_and_preferences(client: httpx.AsyncClient) -> None:
    body = (await client.get("/me", headers=auth(ALICE))).json()
    assert body["email"] == "user-alice@example.com"
    assert body["preferences"] == {"allergens": [], "diets": [], "save_history": True}
    prefs = {"allergens": ["sesame", "milk", "milk"], "diets": ["vegan"], "save_history": True}
    r = await client.put("/me/preferences", json=prefs, headers=auth(ALICE))
    assert r.json()["allergens"] == ["milk", "sesame"]
    assert (await client.get("/me", headers=auth(ALICE))).json()["preferences"]["diets"] == [
        "vegan"
    ]
    bad = await client.put("/me/preferences", json={"allergens": ["mustard"]}, headers=auth(ALICE))
    assert bad.status_code == 422


@spec("ACC-9", "ACC-10")
@pytest.mark.usefixtures("accounts")
async def test_history_saves_the_score_then_dedupes_repeat_views(client: httpx.AsyncClient) -> None:
    assert (await scan(client, ALICE)).status_code == 201
    again = await scan(client, ALICE)
    assert again.status_code == 200 and again.json() == {"saved": False, "reason": "recent"}
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=11)
    assert (await scan(client, ALICE)).status_code == 201
    assert (await scan(client, ALICE, OTHER)).status_code == 201
    items = (await client.get("/me/history", headers=auth(ALICE))).json()["items"]
    assert [i["gtin"] for i in items] == [OTHER, GTIN, GTIN]  # newest first
    assert items[1]["total"] == 41 and items[1]["band"] == {"id": "mediocre", "label": "Mediocre"}
    assert items[0]["name"] == "Other Bars"


@spec("ACC-10")
@pytest.mark.usefixtures("accounts")
async def test_history_pages_with_a_cursor(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(me_router, "PAGE", 2)
    for minutes in range(0, 50, 11):
        app.dependency_overrides[get_now] = lambda m=minutes: NOW + timedelta(minutes=m)
        await scan(client, ALICE)
    first = (await client.get("/me/history", headers=auth(ALICE))).json()
    second = (
        await client.get(f"/me/history?cursor={first['next_cursor']}", headers=auth(ALICE))
    ).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 2
    assert first["items"][-1]["id"] > second["items"][0]["id"]


@spec("ACC-5", "ACC-9")
@pytest.mark.usefixtures("accounts")
async def test_paused_history_saves_nothing(client: httpx.AsyncClient) -> None:
    await client.put("/me/preferences", json={"save_history": False}, headers=auth(ALICE))
    r = await scan(client, ALICE)
    assert r.json() == {"saved": False, "reason": "paused"}
    assert (await client.get("/me/history", headers=auth(ALICE))).json()["items"] == []


@spec("ACC-17")
@pytest.mark.usefixtures("accounts")
async def test_only_the_newest_scans_are_kept(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(me_router, "HISTORY_CAP", 2)
    for minutes in (0, 11, 22):
        app.dependency_overrides[get_now] = lambda m=minutes: NOW + timedelta(minutes=m)
        await scan(client, ALICE)
    await scan(client, BOB)
    assert len((await client.get("/me/history", headers=auth(ALICE))).json()["items"]) == 2
    assert len((await client.get("/me/history", headers=auth(BOB))).json()["items"]) == 1


@spec("ACC-11")
@pytest.mark.usefixtures("accounts")
async def test_delete_one_scan_or_all(client: httpx.AsyncClient) -> None:
    one = (await scan(client, ALICE)).json()["id"]
    await scan(client, ALICE, OTHER)
    deleted = await client.delete(f"/me/history/{one}", headers=auth(ALICE))
    assert deleted.status_code == 204
    deleted = await client.delete(f"/me/history/{one}", headers=auth(ALICE))
    assert deleted.status_code == 404
    deleted = await client.delete("/me/history", headers=auth(ALICE))
    assert deleted.json() == {"deleted": 1}


@spec("ACC-12")
@pytest.mark.usefixtures("accounts")
async def test_favorites(client: httpx.AsyncClient) -> None:
    for _ in range(2):  # idempotent
        assert (await client.put(f"/me/favorites/{GTIN}", headers=auth(ALICE))).status_code == 204
    items = (await client.get("/me/favorites", headers=auth(ALICE))).json()["items"]
    assert [(i["gtin"], i["total"]) for i in items] == [(GTIN, 41)]
    deleted = await client.delete(f"/me/favorites/{GTIN}", headers=auth(ALICE))
    assert deleted.status_code == 204
    assert (await client.get("/me/favorites", headers=auth(ALICE))).json()["items"] == []
    missing = await client.put("/me/favorites/4006381333931", headers=auth(ALICE))
    assert missing.status_code == 404


@spec("ACC-14")
@pytest.mark.usefixtures("accounts")
async def test_users_cannot_see_or_touch_each_others_rows(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    alice_scan = (await scan(client, ALICE)).json()["id"]
    await client.put(f"/me/favorites/{GTIN}", headers=auth(ALICE))
    assert (await client.get("/me/history", headers=auth(BOB))).json()["items"] == []
    assert (await client.get("/me/favorites", headers=auth(BOB))).json()["items"] == []
    deleted = await client.delete(f"/me/history/{alice_scan}", headers=auth(BOB))
    assert deleted.status_code == 404
    await client.delete("/me/history", headers=auth(BOB))
    assert len((await client.get("/me/history", headers=auth(ALICE))).json()["items"]) == 1

    # Below the API: as ofs_app, the policies hide and protect other users' rows.
    async with sessionmaker() as s, s.begin():
        await s.execute(text("SET LOCAL ROLE ofs_app"))
        await s.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": BOB})
        assert await s.scalar(text("SELECT count(*) FROM scan_history")) == 0
        assert await s.scalar(text("SELECT count(*) FROM favorites")) == 0
        with pytest.raises(Exception, match="row-level security"):
            await s.execute(text(
                "INSERT INTO scan_history (user_id, gtin) VALUES (:alice, :g)"
            ), {"alice": ALICE, "g": GTIN})  # fmt: skip


@spec("ACC-13", "ACC-18")
@pytest.mark.usefixtures("accounts")
async def test_deleting_the_account_removes_everything_but_keeps_contributions_unlinked(
    client: httpx.AsyncClient, sessionmaker: Maker
) -> None:
    nutrition = {"energy_kj": 1700, "sugars_g": 20, "saturated_fat_g": 2, "salt_g": 0.5}
    contribution: dict[str, Any] = {"gtin": "0000000000024", "name": "Granola", "kind": "food",
                                    "nutrition": nutrition}  # fmt: skip
    assert (
        await client.post("/contributions", json=contribution, headers=auth(ALICE))
    ).status_code == 201
    mine = (await client.get("/me/contributions", headers=auth(ALICE))).json()["items"]
    assert [c["gtin"] for c in mine] == ["0000000000024"]
    await scan(client, ALICE)
    await client.put(f"/me/favorites/{GTIN}", headers=auth(ALICE))
    await client.put("/me/preferences", json={"diets": ["vegan"]}, headers=auth(ALICE))
    await scan(client, BOB)

    deleted = await client.delete("/me", headers=auth(ALICE))

    assert deleted.status_code == 204
    async with sessionmaker() as s:
        assert await s.scalar(text('SELECT count(*) FROM "user" WHERE id = :u'), {"u": ALICE}) == 0
        for table in ("scan_history", "favorites", "user_preferences"):
            assert await s.scalar(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"),
                                  {"u": ALICE}) == 0  # fmt: skip
        assert await s.scalar(text("SELECT count(*) FROM scan_history WHERE user_id = :u"),
                              {"u": BOB}) == 1  # fmt: skip
        assert await s.scalar(text("SELECT user_id FROM contributions")) is None
    assert (await client.get("/me", headers=auth(ALICE))).status_code == 401
