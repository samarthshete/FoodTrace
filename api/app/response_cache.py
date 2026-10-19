"""In-memory cache of public GET responses, served stale when the route fails (specs/025)."""

import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response

# CACHE-1: public, user-independent routes only. Never /me, /contributions or auth.
CACHEABLE = re.compile(r"^/(products/[^/]+(/[a-z]+)?|search|explore(/[a-z]+)?|methodology)$")
DROP_HEADERS = {"content-length", "date", "server"}


@dataclass
class Entry:
    stored_at: float
    body: bytes
    headers: dict[str, str]


class ResponseCache:
    def __init__(self, ttl_s: float, max_entries: int, clock: Callable[[], float] = time.monotonic):
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self.clock = clock
        self._entries: OrderedDict[str, Entry] = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self.ttl_s > 0

    def get(self, key: str) -> Entry | None:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)  # CACHE-4: least recently used is dropped first
        return entry

    def fresh(self, entry: Entry) -> bool:
        return self.clock() - entry.stored_at < self.ttl_s

    def put(self, key: str, body: bytes, headers: dict[str, str]) -> None:
        self._entries[key] = Entry(self.clock(), body, headers)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


def _replay(entry: Entry, state: str) -> Response:
    return Response(entry.body, status_code=200, headers={**entry.headers, "X-Cache": state})


async def _read_body(response: Response) -> bytes:
    chunks = [chunk async for chunk in response.body_iterator]  # type: ignore[attr-defined]
    return b"".join(c if isinstance(c, bytes) else c.encode() for c in chunks)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def response_cache(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cache: ResponseCache | None = getattr(request.app.state, "response_cache", None)
        path = request.url.path
        if (
            cache is None
            or not cache.enabled
            or request.method != "GET"
            or not CACHEABLE.match(path)
        ):
            return await call_next(request)
        key = f"{path}?{request.url.query}"
        entry = cache.get(key)
        if entry is not None and cache.fresh(entry):
            return _replay(entry, "hit")  # CACHE-2
        try:
            response = await call_next(request)
        except Exception:
            if entry is not None:
                return _replay(entry, "stale")  # CACHE-3
            raise
        if response.status_code >= 500 and entry is not None:
            return _replay(entry, "stale")
        if response.status_code != 200:
            return response
        body = await _read_body(response)
        headers = {k: v for k, v in response.headers.items() if k.lower() not in DROP_HEADERS}
        cache.put(key, body, headers)
        return Response(body, status_code=200, headers={**headers, "X-Cache": "miss"})
