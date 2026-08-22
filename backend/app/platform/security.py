"""HTTP security dependencies (ADR-0004).

The token travels in `Authorization: Bearer` — not a cross-site cookie — because the
frontend (Netlify) and the API (Render) live on different origins.

Layering note: `platform` is the outermost layer, so depending on a module's *application*
layer is allowed (dependencies point inwards, ARCHITECTURE.md §1). This is the location
08-code.md §2 prescribes for `get_current_assessor` / `require_admin`.
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.resolve_assessor import ExternalIdentity, ResolveAssessor
from app.modules.identity.infrastructure.invitation_repository import (
    SqlAlchemyInvitationRepository,
)
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.auth_local import DEV_USER_HEADER, claims_from_header
from app.platform.clerk import ClerkTokenVerifier, InvalidToken, get_verifier
from app.platform.uow import UnitOfWork, get_uow

bearer_scheme = HTTPBearer(auto_error=False)


def get_verified_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    verifier: Annotated[ClerkTokenVerifier, Depends(get_verifier)],
) -> dict[str, Any]:
    """The only place a request becomes an identity — Clerk's JWT or, in local mode, a header.

    The choice is made per request (not at import time) so the mode is testable without
    rebuilding the app. In `clerk` mode the dev header is not read at all: this is a second
    adapter, not a fallback that could be triggered by omitting the token (ADR-0008).
    """
    if get_settings().is_local_auth:
        try:
            return dict(claims_from_header(request))
        except InvalidToken as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_crossed_modes(request, expected="local") or str(exc),
            ) from exc

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_crossed_modes(request, expected="clerk") or "missing bearer token",
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


# The two halves of ADR-0008's seam are configured separately — `AUTH_MODE` in the backend's
# environment, `NEXT_PUBLIC_AUTH_MODE` in the frontend's — so they can disagree, and when they
# do EVERY request fails 401. "missing bearer token" then sends a reader looking for an
# expired session; nothing is wrong with the session, the two sides are not the same app.
#
# The evidence is in the request: a caller built for the other mode sends the other mode's
# credential. So the mismatch is named instead of being reported as an absence.
_MISMATCH = {
    # (mode this API runs in) -> (what a caller in the OTHER mode sends, and the sentence)
    "local": (
        "authorization",
        "this API runs with AUTH_MODE=local and reads the "
        f"{DEV_USER_HEADER} header, but the request carries a bearer token",
    ),
    "clerk": (
        DEV_USER_HEADER.lower(),
        f"this API runs with AUTH_MODE=clerk and expects a bearer token, but the request "
        f"carries {DEV_USER_HEADER}",
    ),
}

_REMEDY = (
    "The frontend and the backend are configured for different auth modes. Set AUTH_MODE in "
    "backend/.env and NEXT_PUBLIC_AUTH_MODE in frontend/.env.local to the same mode, then "
    "restart both - neither value is re-read while running."
)


def _crossed_modes(request: Request, expected: str) -> str | None:
    """The sentence for a request that was built for the other mode, or None.

    ASCII only: this text also reaches a terminal through the CLI and curl, and a Windows
    console (cp1252) raises on anything else.
    """
    header, complaint = _MISMATCH[expected]
    if request.headers.get(header):
        return f"{complaint}. {_REMEDY}"
    return None


def _is_verified(claim: Any) -> bool:
    """Read `email_verified` without letting the string `"false"` mean verified.

    A JWT template can send this either way. A bare shortcode keeps the original type and
    arrives as a boolean; a **quoted** one — `"email_verified": "{{user.email_verified}}"` —
    is interpolated, and Clerk documents that interpolated shortcodes always produce strings.
    So the claim is legitimately `False` or `"false"`, and `bool("false")` is `True`: the one
    reading that turns an unverified address into a verified one, which is exactly what this
    gate exists to prevent (ADR-0049 §3).

    Anything unrecognised is not verified. The claim is a statement somebody has to make, and
    a value nobody can interpret is not that statement.
    """
    if isinstance(claim, bool):
        return claim
    if isinstance(claim, str):
        return claim.strip().lower() == "true"
    return False


def get_current_assessor(
    claims: Annotated[dict[str, Any], Depends(get_verified_claims)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> AssessorDTO:
    """Resolve the verified Clerk identity into our `Assessor`, creating it on first login.

    `email` and `name` require a JWT template in Clerk; both are optional so a missing
    template degrades the profile instead of blocking the login. `email_verified` belongs to
    the same template and gates one thing only — redeeming an invitation (ADR-0049); absent,
    it reads as unverified, which refuses to redeem rather than trusting an address nobody
    vouched for.
    """
    identity = ExternalIdentity(
        # Which adapter answered is what the credential's provider means: the same `sub`
        # from two providers is two people (ADR-0004, ADR-0008).
        provider=get_settings().auth_mode,
        subject=claims["sub"],
        email=claims.get("email"),
        display_name=claims.get("name"),
        email_verified=_is_verified(claims.get("email_verified")),
    )
    resolve = ResolveAssessor(
        SqlAlchemyAssessorRepository(uow.session),
        SqlAlchemyInvitationRepository(uow.session),
        uow.events,
        uow,
        # Bootstrap allowlist: only ever applied when creating a new assessor.
        bootstrap_admins=get_settings().bootstrap_admin_emails,
    )
    assessor = resolve(identity)

    # Offboarding is a state, not a deletion (ADR-0051) — and a state that only removed
    # somebody from pickers would be cosmetic: their credential would still open every
    # door. Refused here, at the one place a request becomes an identity, so no handler can
    # be the one that forgot.
    if not assessor.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this account is deactivated",
        )
    return assessor


def require_admin(
    assessor: Annotated[AssessorDTO, Depends(get_current_assessor)],
) -> AssessorDTO:
    if not assessor.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return assessor


def require_local_mode() -> None:
    """A dev-only surface does not exist outside `AUTH_MODE=local` (ADR-0008).

    Declared on the router rather than checked inside each handler so it resolves *before*
    any auth dependency: a 401 would confirm the path exists to anyone who asked, and the
    gate would be one handler away from being forgotten (ADR-0035 §3). Read per request,
    like the mode itself, so it is testable without rebuilding the app.
    """
    if not get_settings().is_local_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")


VerifiedClaims = Annotated[dict[str, Any], Depends(get_verified_claims)]
CurrentAssessor = Annotated[AssessorDTO, Depends(get_current_assessor)]
AdminAssessor = Annotated[AssessorDTO, Depends(require_admin)]
