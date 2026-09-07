"""Configuring the Clerk instance itself, before anybody signs in (ADR-0004, ADR-0007).

One act lives here, and it is here rather than in a dashboard checklist because getting it
wrong cannot be repaired from inside the product. Clerk's default session token carries
neither email nor name. Without a JWT template that adds them, the first admin is created as
an `evaluator` — the safe degrade — and `ADMIN_EMAILS` applies **once, at row creation**, so
writing the template afterwards rescues nobody. Two individually correct behaviours whose
order is the whole risk, and the symptom is silence: the person signs in, appears in the
roster with the wrong role, and nothing anywhere says why.

So the shortcodes are written down here instead of retyped into a form. `{{user.email_verified}}`
in particular has several plausible spellings and only one right one, and the one thing it
gates — redeeming an invitation (ADR-0049) — fails quietly too.

This is on no request path. `clerk.py` verifies the tokens this makes worth verifying.
"""

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.platform import clerk_api

# The name the frontend asks for its token by (`NEXT_PUBLIC_CLERK_JWT_TEMPLATE`). The two have
# to agree: `getToken({ template })` against a name Clerk does not have returns nothing, and
# the request arrives unauthenticated rather than wrong.
TEMPLATE_NAME = "learnpack-evals"

# What the backend reads off a verified token: `email` decides the initial role (ADR-0007) and
# identifies an SME, `name` is what a reader of a judgment sees, and `email_verified` gates
# redeeming an invitation — matching an invitation on an address the provider never vouched
# for is a known account-takeover shape (ADR-0049).
CLAIMS: dict[str, str] = {
    "email": "{{user.primary_email_address}}",
    "name": "{{user.full_name}}",
    "email_verified": "{{user.email_verified}}",
}

JWT_TEMPLATES_URL = f"{clerk_api.API_BASE}/jwt_templates"


class ClerkSetupFailed(Exception):
    """Clerk could not be reached, or refused. Carries its own sentence where it gave one."""


@dataclass(frozen=True)
class TemplateOutcome:
    """What the act did, so a runbook step can report itself.

    `unchanged` is a real outcome and not a failure: this is run again after every change to
    the environment, and a template already right is the answer that says so.
    """

    action: Literal["created", "updated", "unchanged"]
    template_id: str
    name: str


def ensure_jwt_template(
    secret_key: str,
    name: str = TEMPLATE_NAME,
    claims: dict[str, str] | None = None,
) -> TemplateOutcome:
    """Make the instance behind `secret_key` carry this template, and say what that took."""
    wanted = dict(claims if claims is not None else CLAIMS)
    existing = _template_named(secret_key, name)

    if existing is None:
        created = _request(secret_key, "POST", JWT_TEMPLATES_URL, {"name": name, "claims": wanted})
        return TemplateOutcome("created", str(created.get("id", "")), name)

    template_id = str(existing.get("id", ""))
    if existing.get("claims") == wanted:
        return TemplateOutcome("unchanged", template_id, name)

    _request(
        secret_key,
        "PATCH",
        f"{JWT_TEMPLATES_URL}/{template_id}",
        {"name": name, "claims": wanted},
    )
    return TemplateOutcome("updated", template_id, name)


def _template_named(secret_key: str, name: str) -> dict[str, Any] | None:
    """The instance's template by that name, or None.

    Listed rather than fetched by id because the id is Clerk's and the name is ours: the name
    is what the frontend asks for a token by, so it is the only handle a runbook has.
    """
    listed = _request(secret_key, "GET", JWT_TEMPLATES_URL, None)
    # Clerk's list endpoints answer either a bare array or `{"data": [...]}` depending on the
    # resource, and reading the wrong one here would find no template and mint a second.
    templates = listed.get("data") if isinstance(listed, dict) else listed
    if not isinstance(templates, list):
        raise ClerkSetupFailed(f"could not read the JWT templates: unexpected answer {listed!r}")
    return next(
        (t for t in templates if isinstance(t, dict) and t.get("name") == name),
        None,
    )


def _request(secret_key: str, method: str, url: str, body: dict[str, Any] | None) -> Any:
    try:
        response = httpx.request(
            method,
            url,
            headers={"Authorization": f"Bearer {secret_key}"},
            json=body,
            timeout=clerk_api.TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise ClerkSetupFailed(f"could not reach Clerk: {exc}") from exc

    if not response.is_success:
        sentence = clerk_api.error_sentence(response)
        raise ClerkSetupFailed(
            f"Clerk refused {method} {url} ({response.status_code})"
            + (f": {sentence}" if sentence else "")
        )

    try:
        return response.json()
    except ValueError as exc:  # pragma: no cover — a success that is not JSON
        raise ClerkSetupFailed(f"Clerk answered {method} {url} with no JSON body") from exc
