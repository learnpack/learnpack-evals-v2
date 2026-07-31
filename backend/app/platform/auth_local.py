"""Local identity for development: the claims come from a header, unverified (ADR-0008).

The counterpart of `clerk.py` — same layer, same job, same output — so that everything
downstream (`ResolveAssessor`, roles, `require_admin`) stays exactly the same code. This is
the seam the test suite already uses: `tests/conftest.py::as_user` overrides nothing but the
claims, and the whole authorisation chain runs for real.

There is no signature to check here: the mode exists so contributors working on rubrics,
metrics and evaluations can run the app with no accounts and no cloud. `Settings` refuses to
combine it with `ENVIRONMENT=production`.
"""

from fastapi import Request

from app.platform.clerk import InvalidToken

# Who you are, in local mode. Plain text, no token: that is the whole point.
DEV_USER_HEADER = "X-Dev-User"


def display_name_for(email: str) -> str:
    """`ada.lovelace@local.dev` → `Ada Lovelace`, so the UI has something to show."""
    local_part = email.split("@", 1)[0]
    for separator in ("_", "-"):
        local_part = local_part.replace(separator, ".")
    return " ".join(part.capitalize() for part in local_part.split(".") if part)


def claims_from_header(request: Request) -> dict[str, str | None]:
    """Build the same claim shape Clerk returns, from `X-Dev-User: <email>`.

    `sub` is namespaced (`local|<email>`) so a local assessor can never collide with a real
    Clerk user id if the same database is ever reused.
    """
    email = (request.headers.get(DEV_USER_HEADER) or "").strip()
    if not email:
        raise InvalidToken(f"missing {DEV_USER_HEADER} header (AUTH_MODE=local)")

    return {"sub": f"local|{email.lower()}", "email": email, "name": display_name_for(email)}
