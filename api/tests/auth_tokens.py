"""Sign test JWTs the way the web app's Better Auth does (Ed25519, published as a JWKS)."""

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.algorithms import OKPAlgorithm

WEB = "https://web.test"
JWKS_URL = f"{WEB}/api/auth/jwks"
KID = "test-key"
_KEY = Ed25519PrivateKey.generate()


def jwks() -> dict[str, Any]:
    jwk = json.loads(OKPAlgorithm.to_jwk(_KEY.public_key()))
    return {"keys": [{**jwk, "kid": KID, "alg": "EdDSA"}]}


def token(
    sub: str,
    *,
    ttl: int = 900,
    aud: str = WEB,
    iss: str = WEB,
    kid: str = KID,
    signer: Ed25519PrivateKey | None = None,  # a different key forges the signature
) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iat": now, "exp": now + ttl, "aud": aud, "iss": iss}
    return jwt.encode(claims, signer or _KEY, algorithm="EdDSA", headers={"kid": kid})
