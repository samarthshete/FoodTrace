import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.auth import JWKSCache, verify
from app.problems import Problem
from app.routers.me import PreferencesIn
from app.settings import Settings

from ..auth_tokens import JWKS_URL, WEB, jwks, token

spec = pytest.mark.spec
SETTINGS = Settings(auth_jwks_url=JWKS_URL, auth_issuer=WEB, auth_audience=WEB)


async def check(tok: str) -> str:
    async with httpx.AsyncClient() as http, respx.mock as mock:
        mock.get(JWKS_URL).respond(200, json=jwks())
        return await verify(tok, http, JWKSCache(), SETTINGS)


@spec("ACC-3")
async def test_a_valid_better_auth_token_gives_the_user_id() -> None:
    assert await check(token("user-1")) == "user-1"


@spec("ACC-3")
@pytest.mark.parametrize(
    "bad",
    [token("u", ttl=-60), token("u", aud="https://other.test"), token("u", iss="https://evil.test"),
     token("u", kid="unknown"), token("u", signer=Ed25519PrivateKey.generate()), "not-a-jwt"],
    ids=["expired", "wrong-audience", "wrong-issuer", "unknown-key", "forged", "garbage"],
)  # fmt: skip
async def test_invalid_tokens_are_401(bad: str) -> None:
    with pytest.raises(Problem) as err:
        await check(bad)
    assert err.value.status == 401


@spec("ACC-3")
async def test_keys_are_cached_between_requests() -> None:
    cache = JWKSCache()
    async with httpx.AsyncClient() as http, respx.mock as mock:
        route = mock.get(JWKS_URL).respond(200, json=jwks())
        for _ in range(3):
            assert await verify(token("u"), http, cache, SETTINGS) == "u"
    assert route.call_count == 1


@spec("ACC-5")
def test_preferences_accept_only_the_major_nine_and_known_diets() -> None:
    prefs = PreferencesIn(allergens=["milk", "sesame"], diets=["vegan"])
    assert prefs.save_history is True  # on by default
    with pytest.raises(ValidationError):
        PreferencesIn(allergens=["mustard"])
    with pytest.raises(ValidationError):
        PreferencesIn(diets=["keto"])
