"""HTTP security dependencies (ADR-0004).

The token travels in `Authorization: Bearer` — not a cross-site cookie — because the
frontend (Netlify) and the API (Render) live on different origins.

Block 1 stops at cryptographic verification. Resolving the claims into an `Assessor`
(`get_current_assessor`) and `require_admin` belong to the identity module (block 2).
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.platform.clerk import ClerkTokenVerifier, InvalidToken, get_verifier

bearer_scheme = HTTPBearer(auto_error=False)


def get_verified_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[ClerkTokenVerifier, Depends(get_verifier)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verifier.verify(credentials.credentials)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


VerifiedClaims = Annotated[dict[str, Any], Depends(get_verified_claims)]
