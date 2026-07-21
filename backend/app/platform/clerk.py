"""Clerk JWT verification against the provider's JWKS (ADR-0004).

This is the outermost edge of Identity. The domain only ever sees an `assessorId`;
swapping Clerk for another provider stops here.
"""

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.config import Settings, get_settings


class InvalidToken(Exception):
    """The bearer token is missing, malformed, expired or not signed by Clerk."""


class ClerkTokenVerifier:
    """Verifies signature, issuer and expiry. Caches the JWKS between calls."""

    def __init__(self, settings: Settings | None = None, jwks_client: PyJWKClient | None = None):
        self._settings = settings or get_settings()
        self._jwks_client = jwks_client
        # An injected client is used as-is and never rotated (tests supply a fake one);
        # only self-built clients expire, because Clerk rotates its signing keys.
        self._owns_client = jwks_client is None
        self._fetched_at = 0.0
        self._jwks_ttl_seconds = 3600

    def _client(self) -> PyJWKClient:
        if not self._owns_client:
            assert self._jwks_client is not None
            return self._jwks_client
        expired = time.monotonic() - self._fetched_at > self._jwks_ttl_seconds
        if self._jwks_client is None or expired:
            self._jwks_client = PyJWKClient(self._settings.jwks_url, cache_keys=True)
            self._fetched_at = time.monotonic()
        return self._jwks_client

    def verify(self, token: str) -> dict[str, Any]:
        """Return the verified claims, or raise `InvalidToken`.

        `sub` is Clerk's user id — the identity module maps it to an `Assessor` (block 2).
        """
        if not token:
            raise InvalidToken("missing token")
        try:
            signing_key = self._client().get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._settings.clerk_issuer,
                options={"require": ["exp", "sub", "iss"], "verify_aud": False},
            )
        except (jwt.PyJWTError, httpx.HTTPError) as exc:
            raise InvalidToken(str(exc)) from exc


_verifier: ClerkTokenVerifier | None = None


def get_verifier() -> ClerkTokenVerifier:
    global _verifier
    if _verifier is None:
        _verifier = ClerkTokenVerifier()
    return _verifier
