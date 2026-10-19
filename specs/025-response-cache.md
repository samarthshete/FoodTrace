# 025: Response cache

Status: implemented

The hosted database is a network hop away, so every product page costs several round trips, and
a dropped connection used to mean "Try again in a moment". The API keeps a small in-memory copy
of recent public responses, which makes repeat views instant and survives short database or
network outages.

- **CACHE-1** Only `GET` requests to public, user-independent routes are cached:
  `/products/…`, `/search`, `/explore…` and `/methodology`. Nothing under `/me`, `/contributions`
  or `/api/auth` is ever cached (privacy rule 6). The key is the path plus the query string.
- **CACHE-2** Only `200` responses are stored, for `RESPONSE_CACHE_TTL_S` seconds (default 300,
  the same as the routes' `Cache-Control`). A fresh entry is served without touching the
  database, with `X-Cache: hit`; a stored response gets `X-Cache: miss`.
- **CACHE-3** If the route fails (an exception or a `5xx`) and an entry exists, however old, it
  is served instead with `X-Cache: stale`. Without an entry the error passes through unchanged.
- **CACHE-4** At most `RESPONSE_CACHE_MAX` entries (default 2,000); the least recently used is
  dropped first. `RESPONSE_CACHE_TTL_S=0` turns caching off (tests use this). The cache is per
  process and lost on restart.
