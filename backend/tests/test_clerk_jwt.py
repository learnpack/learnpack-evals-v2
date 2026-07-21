"""Clerk token verification (ADR-0004) — signs tokens with a local RSA key and checks
them against a fake JWKS, so no network and no Clerk account are involved.
"""

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import Settings
from app.platform.clerk import ClerkTokenVerifier, InvalidToken

ISSUER = "https://example.clerk.accounts.dev"
KID = "test-key"


@pytest.fixture(scope="module")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJWKClient:
    """Stands in for PyJWKClient: returns the matching key without any HTTP call."""

    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        jwk["kid"] = KID
        self._signing_key = jwt.PyJWK(jwk, algorithm="RS256")

    def get_signing_key_from_jwt(self, token: str):  # noqa: ANN201 — mirrors PyJWKClient
        header = jwt.get_unverified_header(token)
        if header.get("kid") != KID:
            raise jwt.PyJWKClientError("no matching key")
        return self._signing_key


def make_verifier(private_key: rsa.RSAPrivateKey) -> ClerkTokenVerifier:
    settings = Settings(database_url="", clerk_issuer=ISSUER)
    return ClerkTokenVerifier(settings=settings, jwks_client=_FakeJWKClient(private_key))


def make_token(private_key: rsa.RSAPrivateKey, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": "user_abc123",
        "iss": ISSUER,
        "exp": now + timedelta(minutes=5),
        "iat": now,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": KID})


def test_valid_token_returns_claims(private_key):
    claims = make_verifier(private_key).verify(make_token(private_key))
    assert claims["sub"] == "user_abc123"
    assert claims["iss"] == ISSUER


def test_expired_token_is_rejected(private_key):
    expired = make_token(private_key, exp=datetime.now(UTC) - timedelta(minutes=1))
    with pytest.raises(InvalidToken):
        make_verifier(private_key).verify(expired)


def test_wrong_issuer_is_rejected(private_key):
    token = make_token(private_key, iss="https://attacker.example.com")
    with pytest.raises(InvalidToken):
        make_verifier(private_key).verify(token)


def test_token_signed_by_another_key_is_rejected(private_key):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(other_key)
    with pytest.raises(InvalidToken):
        make_verifier(private_key).verify(token)


def test_missing_token_is_rejected(private_key):
    with pytest.raises(InvalidToken):
        make_verifier(private_key).verify("")
