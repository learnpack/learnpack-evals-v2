"""Adapters for `SeatProviderPort` (ADR-0061) — the platform that serves the course.

Two services sit behind this one port, and that is not an accident of implementation: the
course platform issues the identity and the AI service verifies it against that platform. A
seat is only usable once both know about it, so both live here rather than leaking two ports
into the application layer, which would have to know why there are two.

The credentials are injected by constructor and never read from settings inside the class,
like `identity/infrastructure/dispatchers.py`. `httpx` is used at module level for the same
reason it is there: a test patches the name and the request is built for real without ever
leaving the process.

**Nothing here logs a token.** The provider returns one and the caller passes it straight to
the page that needs it; a token in a log file is a session anybody reading logs can take.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.modules.course_session.application.ports import ExternalSeat, SeatProvisioningFailed

logger = logging.getLogger(__name__)

# The platform that issues the identity, and the name the seat is stored under.
PROVIDER_NAME = "breathecode"

STUDENT_PATH = "/v1/auth/academy/student"
COHORT_USER_PATH = "/v1/admissions/academy/cohort/{cohort_id}/user"
MEMBER_TOKEN_PATH = "/v1/auth/member/{subject}/token"
# v2, not v1: the older invite endpoint answers a 500 with the whole traceback in the body.
AI_INVITE_PATH = "/v2/auth/invite"

# Longer than the 10 s an invitation gets, because this runs while somebody waits for a
# course to open and two of the four calls fan out to a second service upstream.
TIMEOUT_SECONDS = 15.0


class UnconfiguredSeatProvider:
    """No platform to talk to — under `AUTH_MODE=local`, or with the credentials unset.

    Not a no-op that pretends to succeed: a fake seat would be written to the database and
    the page would carry a token that opens nothing. Refusing with the reason is what lets
    the endpoint say "the course is here, the AI is not, and this is why".
    """

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def _refuse(self) -> SeatProvisioningFailed:
        return SeatProvisioningFailed(self._reason)

    def create_seat(self, email: str, display_name: str) -> ExternalSeat:
        raise self._refuse()

    def enroll(self, seat: ExternalSeat) -> None:
        raise self._refuse()

    def mint_token(self, seat: ExternalSeat) -> str:
        raise self._refuse()

    def enable_ai(self, seat: ExternalSeat, token: str) -> None:
        raise self._refuse()


class BreatheCodeSeatProvider:
    """The real thing: an academy membership on the course platform, known to the AI service."""

    def __init__(
        self,
        api_url: str,
        service_token: str,
        academy_id: str,
        cohort_id: str,
        ai_api_url: str,
        ai_organization: str,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._service_token = service_token
        self._academy_id = academy_id
        self._cohort_id = cohort_id
        self._ai_api_url = ai_api_url.rstrip("/")
        self._ai_organization = ai_organization

    # ------------------------------------------------------------------- the four acts

    def create_seat(self, email: str, display_name: str) -> ExternalSeat:
        first_name, _, last_name = display_name.partition(" ")
        body = self._post(
            f"{self._api_url}{STUDENT_PATH}",
            headers=self._headers(),
            json={
                "email": email,
                "first_name": first_name or "SME",
                "last_name": last_name or "Seat",
                # Required for an address nobody has yet: without it the platform refuses
                # rather than creating one.
                "invite": True,
            },
            act="create the seat",
        )

        subject = body.get("id")
        user_id = (body.get("user") or {}).get("id")
        if subject is None or user_id is None:
            # The membership may well exist by now, so the message carries what we did get:
            # somebody has to be able to find it rather than hunt for an orphan by email.
            raise SeatProvisioningFailed(
                f"the seat for {email} was created but the response named no "
                f"{'membership' if subject is None else 'account'} id, so it cannot be "
                f"enrolled (membership={subject!r})"
            )
        return ExternalSeat(provider=PROVIDER_NAME, subject=str(subject), user_id=str(user_id))

    def enroll(self, seat: ExternalSeat) -> None:
        """Put the seat in the cohort that grants its AI allowance.

        The allowance is not a property of the account but of being an up-to-date student in
        a non-SaaS cohort, which is what the platform reads before it hands out the virtual
        consumables the course page checks. A seat outside a cohort loads the course and is
        refused the moment it asks the AI to run anything.
        """
        self._post(
            f"{self._api_url}{COHORT_USER_PATH.format(cohort_id=self._cohort_id)}",
            headers=self._headers(),
            # The platform validates this as an integer and rejects a string.
            json={
                "user": int(seat.user_id),
                "role": "STUDENT",
                # `finantial_status` is deliberately absent: the allowance is refused for
                # LATE and granted for anything else, so saying nothing is the safe value.
                "educational_status": "ACTIVE",
            },
            act="enrol the seat in the campaign cohort",
        )

    def mint_token(self, seat: ExternalSeat) -> str:
        body = self._post(
            f"{self._api_url}{MEMBER_TOKEN_PATH.format(subject=seat.subject)}",
            headers=self._headers(),
            json=None,
            act="mint a session for the seat",
        )
        token = body.get("key")
        if not token:
            raise SeatProvisioningFailed("the platform returned no session key for this seat")
        return str(token)

    def enable_ai(self, seat: ExternalSeat, token: str) -> None:
        """Register the seat with the AI service.

        Unauthenticated on purpose: the token in the body *is* the credential, and the AI
        service verifies it upstream against the platform that issued it.
        """
        self._post(
            f"{self._ai_api_url}{AI_INVITE_PATH}",
            headers={"Content-Type": "application/json"},
            json={"organization": self._ai_organization, "user_token": token},
            act="register the seat with the AI service",
        )

    # ------------------------------------------------------------------- transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self._service_token}",
            # How the platform resolves which academy the service account is acting for.
            "Academy": self._academy_id,
            "Content-Type": "application/json",
        }

    def _post(
        self,
        url: str,
        headers: dict[str, str],
        json: dict[str, Any] | None,
        act: str,
    ) -> dict[str, Any]:
        try:
            response = httpx.post(url, headers=headers, json=json, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise SeatProvisioningFailed(f"could not {act}: {exc}") from exc

        if not response.is_success:
            raise SeatProvisioningFailed(f"could not {act} - {_explain(response)}")

        return _body(response)


def _body(response: httpx.Response) -> dict[str, Any]:
    """The response as a mapping, or an empty one. A 201 with no body is not a failure."""
    try:
        parsed = response.json()
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _explain(response: httpx.Response) -> str:
    """The provider's own sentence when it has one.

    Both services answer with `{"detail": ...}` and sometimes a `slug`. The generic status
    code is what nobody can act on; "this academy is not active" is.
    """
    detail = ""
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            raw = parsed.get("detail") or parsed.get("error") or parsed.get("message") or ""
            detail = raw if isinstance(raw, str) else str(raw)
    except ValueError:
        detail = ""
    return f"the platform answered {response.status_code}" + (f": {detail}" if detail else "")


def get_seat_provider() -> UnconfiguredSeatProvider | BreatheCodeSeatProvider:
    """Which adapter this process provisions with. Read per call, like the auth mode itself,
    so the choice is testable without rebuilding the app.

    Missing configuration degrades to a refusal that names what is missing, rather than
    failing at boot: the product works without course sessions — every screen except the AI
    inside the iframe — and a deploy that has not been given these credentials should say so
    on that one screen, not refuse to start.
    """
    settings = get_settings()

    if settings.is_local_auth:
        return UnconfiguredSeatProvider(
            "AUTH_MODE=local: no course session is minted here, because there are no "
            "accounts and no cloud. The course still loads without its AI."
        )

    missing = [
        name
        for name, value in (
            ("BREATHECODE_SERVICE_TOKEN", settings.breathecode_service_token),
            ("BREATHECODE_ACADEMY_ID", settings.breathecode_academy_id),
            ("BREATHECODE_COHORT_ID", settings.breathecode_cohort_id),
        )
        if not value.strip()
    ]
    if missing:
        logger.warning(
            "course sessions are disabled: %s not set, so the evaluator's course loads "
            "without its AI",
            ", ".join(missing),
        )
        return UnconfiguredSeatProvider(
            f"this deployment has no course-session credentials ({', '.join(missing)} not "
            f"set), so the course loads without its AI"
        )

    return BreatheCodeSeatProvider(
        api_url=settings.breathecode_api_url,
        service_token=settings.breathecode_service_token,
        academy_id=settings.breathecode_academy_id,
        cohort_id=settings.breathecode_cohort_id,
        ai_api_url=settings.rigobot_api_url,
        ai_organization=settings.rigobot_organization,
    )
