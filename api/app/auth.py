"""Verify Better Auth JWTs from the web app (specs/018, ACC-3).

The web app's Better Auth (jwt plugin) signs short-lived tokens with an Ed25519 key and
publishes the public keys at /api/auth/jwks. Keys are cached and refetched when a token
names a key we haven't seen.
"""

import time
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Request

from app.problems import Problem
from app.settings import Settings, get_settings

JWKS_TTL_S = 3600
ALGORITHMS = ["EdDSA", "ES256", "RS256"]


class JWKSCache:
    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched = 0.0

    async def key(self, kid: str, url: str, http: httpx.AsyncClient) -> Any:
        stale = time.monotonic() - self._fetched > JWKS_TTL_S
        if kid not in self._keys or stale:
            resp = await http.get(url, timeout=5)
            resp.raise_for_status()
            self._keys = {k["kid"]: jwt.PyJWK(k).key for k in resp.json().get("keys", [])}
            self._fetched = time.monotonic()
        if kid not in self._keys:
            raise jwt.InvalidKeyError(f"unknown key {kid}")
        return self._keys[kid]


def _unauthorized(detail: str) -> Problem:
    return Problem(401, "Sign in required", detail)


async def verify(token: str, http: httpx.AsyncClient, cache: JWKSCache, settings: Settings) -> str:
    """Return the user id (`sub`) of a valid token, or raise a 401 Problem."""
    try:
        kid = jwt.get_unverified_header(token).get("kid", "")
        key = await cache.key(kid, settings.auth_jwks_url, http)
        claims = jwt.decode(
            token, key, algorithms=ALGORITHMS, audience=settings.auth_audience,
            issuer=settings.auth_issuer, options={"require": ["exp", "sub", "iss", "aud"]},
        )  # fmt: skip
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise _unauthorized("Your session has expired. Sign in again.") from exc
    return str(claims["sub"])


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _cache(request: Request) -> JWKSCache:
    cache: JWKSCache | None = getattr(request.app.state, "jwks", None)
    if cache is None:
        cache = request.app.state.jwks = JWKSCache()
    return cache


async def current_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    """The signed-in user's id; 401 problem+json without a valid token (ACC-3)."""
    token = _bearer(request)
    if token is None:
        raise _unauthorized("Sign in to use your account.")
    return await verify(token, request.app.state.http, _cache(request), settings)


async def optional_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> str | None:
    """The user id if a valid token is sent, else None. A bad token is still a 401."""
    if _bearer(request) is None:
        return None
    return await current_user(request, settings)


UserId = Annotated[str, Depends(current_user)]
MaybeUserId = Annotated[str | None, Depends(optional_user)]
