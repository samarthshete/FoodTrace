"""The in-memory response cache (specs/025)."""

import httpx
import pytest
from fastapi import FastAPI, Response

from app import response_cache
from app.response_cache import ResponseCache

spec = pytest.mark.spec


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_app(cache: ResponseCache | None) -> tuple[FastAPI, dict[str, int]]:
    app = FastAPI()
    calls = {"n": 0, "fail": 0}

    @app.get("/products/{gtin}")
    async def product(gtin: str) -> dict[str, object]:
        calls["n"] += 1
        if calls["fail"] == 1:
            raise RuntimeError("database unreachable")
        if calls["fail"] == 2:
            return Response(status_code=503)  # type: ignore[return-value]
        return {"gtin": gtin, "n": calls["n"]}

    @app.get("/products/{gtin}/missing")
    async def missing(gtin: str) -> Response:
        calls["n"] += 1
        return Response(status_code=404)

    @app.get("/me/history")
    async def history() -> dict[str, int]:
        calls["n"] += 1
        return {"n": calls["n"]}

    app.state.response_cache = cache
    response_cache.install(app)
    return app, calls


def client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://api")


@spec("CACHE-1", "CACHE-2")
async def test_fresh_hits_skip_the_route_and_private_routes_are_never_cached() -> None:
    app, _calls = make_app(ResponseCache(300, 10))
    async with client(app) as c:
        first = await c.get("/products/1")
        second = await c.get("/products/1")
        assert first.headers["x-cache"] == "miss" and second.headers["x-cache"] == "hit"
        assert second.json() == first.json() == {"gtin": "1", "n": 1}
        assert (await c.get("/products/1?x=2")).json()["n"] == 2  # the query is part of the key
        await c.get("/me/history")
        me = await c.get("/me/history")
        assert me.json() == {"n": 4} and "x-cache" not in me.headers


@spec("CACHE-2")
async def test_only_200s_are_stored_and_entries_expire() -> None:
    clock = Clock()
    app, calls = make_app(ResponseCache(300, 10, clock))
    async with client(app) as c:
        await c.get("/products/1/missing")
        assert (await c.get("/products/1/missing")).status_code == 404
        assert calls["n"] == 2
        await c.get("/products/1")
        clock.now = 301
        again = await c.get("/products/1")
        assert again.headers["x-cache"] == "miss" and again.json()["n"] == 4


@spec("CACHE-3")
async def test_failures_serve_the_last_good_copy_however_old() -> None:
    clock = Clock()
    app, calls = make_app(ResponseCache(300, 10, clock))
    async with client(app) as c:
        await c.get("/products/1")
        clock.now = 10_000
        calls["fail"] = 1
        stale = await c.get("/products/1")
        assert stale.status_code == 200 and stale.headers["x-cache"] == "stale"
        assert stale.json() == {"gtin": "1", "n": 1}
        calls["fail"] = 2
        assert (await c.get("/products/1")).headers["x-cache"] == "stale"
        assert (await c.get("/products/2")).status_code == 503  # no copy: the error passes through
        calls["fail"] = 1
        assert (await c.get("/products/3")).status_code == 500


@spec("CACHE-4")
async def test_least_recently_used_is_dropped_and_zero_ttl_disables() -> None:
    cache = ResponseCache(300, 2)
    app, _calls = make_app(cache)
    async with client(app) as c:
        await c.get("/products/1")
        await c.get("/products/2")
        await c.get("/products/1")  # 1 is now the most recently used
        await c.get("/products/3")  # drops 2
        assert cache.get("/products/1?") is not None and cache.get("/products/2?") is None
    off, _calls = make_app(ResponseCache(0, 10))
    async with client(off) as c:
        await c.get("/products/1")
        r = await c.get("/products/1")
        assert r.json()["n"] == 2 and "x-cache" not in r.headers
    none, _calls = make_app(None)
    async with client(none) as c:
        assert "x-cache" not in (await c.get("/products/1")).headers
