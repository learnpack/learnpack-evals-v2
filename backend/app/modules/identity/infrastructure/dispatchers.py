"""Adapters for `InvitationDispatcherPort` (ADR-0049 §8).

Two, chosen by the auth mode — the same seam ADR-0008 already draws for authentication, and
for the same reason: a box with no accounts and no cloud must be able to walk the whole flow.

- `AUTH_MODE=local` → `LoggingInvitationDispatcher`. Nothing is delivered and the log says
  so. The invited address shows up in the local sign-in picker, which is how it is redeemed.
- `AUTH_MODE=clerk` → `ClerkInvitationDispatcher`. Creates the invitation in Clerk, so
  inviting from this console is **one act** instead of two.
"""

import logging

import httpx

from app.config import get_settings
from app.modules.identity.application.ports import InvitationDeliveryFailed
from app.modules.identity.domain.invitation import Invitation
from app.platform import clerk_api

logger = logging.getLogger(__name__)

CLERK_INVITATIONS_URL = f"{clerk_api.API_BASE}/invitations"

TIMEOUT_SECONDS = clerk_api.TIMEOUT_SECONDS


class LoggingInvitationDispatcher:
    """Records that an invitation is waiting, and delivers nothing.

    Not a placeholder: under `AUTH_MODE=local` there is no provider to deliver to, and
    saying so where an operator can read it beats implying an email went out.
    """

    def dispatch(self, invitation: Invitation) -> None:
        logger.info(
            "invitation pending for %s (role=%s, expires=%s) - nothing was delivered "
            "(AUTH_MODE=local); it is redeemed at that address's first sign-in",
            invitation.email,
            invitation.role,
            invitation.expires_at.isoformat() if invitation.expires_at else "never",
        )


class ClerkInvitationDispatcher:
    """Creates the matching invitation in Clerk, which sends the email and lets the person
    through an invite-only instance (ADR-0004).

    **Two invitations, one act.** Ours records who was asked in, with which role and which
    expertise, and is redeemed at first login (ADR-0049); Clerk's is what makes that login
    possible at all. Neither can do the other's job, so both exist — but only one person
    performs one act.
    """

    def __init__(self, secret_key: str, redirect_url: str = "") -> None:
        self._secret_key = secret_key
        self._redirect_url = redirect_url

    def dispatch(self, invitation: Invitation) -> None:
        try:
            response = httpx.post(
                CLERK_INVITATIONS_URL,
                headers={"Authorization": f"Bearer {self._secret_key}"},
                json=self._body(invitation),
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise InvitationDeliveryFailed(f"could not reach Clerk: {exc}") from exc

        if response.is_success:
            logger.info("clerk invitation created for %s", invitation.email)
            return

        raise InvitationDeliveryFailed(_explain(response))

    def _body(self, invitation: Invitation) -> dict:
        body: dict[str, object] = {
            "email_address": invitation.email,
            "notify": True,
            # Without this, re-sending fails outright: Clerk refuses a second invitation for
            # an address that already has one, and re-sending is exactly the case where it
            # does. What it cannot bypass is an address that is already a Clerk **user** —
            # that stays an error, and it is a true one worth reporting.
            "ignore_existing": True,
        }
        if self._redirect_url:
            body["redirect_url"] = self._redirect_url
        if invitation.expires_at is not None:
            # Both windows say the same thing. Clerk's default is 30 days and ours is 7; two
            # different expiry dates for one invitation is a support question waiting to
            # happen.
            days = (invitation.expires_at - _now()).days
            if days >= 1:
                body["expires_in_days"] = days
        return body


def _now():  # noqa: ANN202 — kept tiny so tests can freeze it
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _explain(response: httpx.Response) -> str:
    """This act's words around Clerk's own sentence.

    The generic "delivery failed" is what an admin cannot act on; "that address is already a
    Clerk user" is what they can — and reading it out of the envelope is the same job at every
    Clerk endpoint, so it lives in `platform/clerk_api.py`. What stays here is the half that
    is about invitations.
    """
    detail = clerk_api.error_sentence(response)
    return f"Clerk refused the invitation ({response.status_code})" + (
        f": {detail}" if detail else ""
    )


def get_invitation_dispatcher() -> LoggingInvitationDispatcher | ClerkInvitationDispatcher:
    """Which adapter this process delivers with. Read per call, like the auth mode itself,
    so the choice is testable without rebuilding the app.

    A `clerk` process with no secret key falls back to logging rather than failing every
    invitation: the roster still works, and the missing key is named where somebody looking
    at "why did nobody get an email" will find it.
    """
    settings = get_settings()
    if settings.is_local_auth:
        return LoggingInvitationDispatcher()
    if not settings.clerk_secret_key:
        logger.warning(
            "AUTH_MODE=clerk but CLERK_SECRET_KEY is not set: invitations are recorded here "
            "and NOT created in Clerk, so invited people cannot sign in until somebody "
            "invites them there by hand."
        )
        return LoggingInvitationDispatcher()
    return ClerkInvitationDispatcher(
        secret_key=settings.clerk_secret_key,
        redirect_url=settings.invitation_redirect_url,
    )
