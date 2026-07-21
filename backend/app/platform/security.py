"""HTTP security dependencies (ADR-0004).

The token travels in `Authorization: Bearer` — not a cross-site cookie — because the
frontend (Netlify) and the API (Render) live on different origins.

Layering note: `platform` is the outermost layer, so depending on a module's *application*
layer is allowed (dependencies point inwards, ARCHITECTURE.md §1). This is the location
08-code.md §2 prescribes for `get_current_assessor` / `require_admin`.
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.resolve_assessor import ClerkIdentity, ResolveAssessor
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.clerk import ClerkTokenVerifier, InvalidToken, get_verifier
from app.platform.uow import UnitOfWork, get_uow

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


def get_current_assessor(
    claims: Annotated[dict[str, Any], Depends(get_verified_claims)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> AssessorDTO:
    """Resolve the verified Clerk identity into our `Assessor`, creating it on first login.

    `email` and `name` require a JWT template in Clerk; both are optional so a missing
    template degrades the profile instead of blocking the login.
    """
    identity = ClerkIdentity(
        clerk_user_id=claims["sub"],
        email=claims.get("email"),
        display_name=claims.get("name"),
    )
    resolve = ResolveAssessor(SqlAlchemyAssessorRepository(uow.session), uow)
    return resolve(identity)


def require_admin(
    assessor: Annotated[AssessorDTO, Depends(get_current_assessor)],
) -> AssessorDTO:
    if not assessor.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return assessor


VerifiedClaims = Annotated[dict[str, Any], Depends(get_verified_claims)]
CurrentAssessor = Annotated[AssessorDTO, Depends(get_current_assessor)]
AdminAssessor = Annotated[AssessorDTO, Depends(require_admin)]
