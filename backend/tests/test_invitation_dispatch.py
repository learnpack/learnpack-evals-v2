"""Delivering an invitation to the identity provider (ADR-0049 §8).

No network and no account: `httpx.MockTransport` answers as Clerk would, so what is pinned
down is the request we send and what we do with each answer — including the one that matters
most, a refusal that must not undo an invitation already committed.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.modules.identity.application.ports import InvitationDeliveryFailed
from app.modules.identity.domain.invitation import Invitation
from app.modules.identity.infrastructure import dispatchers
from app.modules.identity.infrastructure.dispatchers import (
    ClerkInvitationDispatcher,
    LoggingInvitationDispatcher,
    get_invitation_dispatcher,
)
from app.shared.domain.ids import new_id


def make_invitation(**overrides) -> Invitation:
    defaults = {
        "id": new_id(),
        "email": "ada@example.com",
        "expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    return Invitation(**(defaults | overrides))


@pytest.fixture
def clerk(monkeypatch):
    """A Clerk that records what it was asked and answers what the test says.

    `httpx.post` is module-level in the adapter, so it is patched with a client bound to a
    mock transport — the request is built for real and never leaves the process.
    """
    sent: list[httpx.Request] = []

    def _clerk(status_code: int = 200, body: dict | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(status_code, json=body if body is not None else {"id": "inv_1"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(
            dispatchers.httpx, "post", lambda url, **kwargs: client.post(url, **kwargs)
        )
        return sent

    return _clerk


# ------------------------------------------------------------------------- the request


def test_it_asks_clerk_to_invite_that_address(clerk):
    sent = clerk()
    ClerkInvitationDispatcher("sk_test_x", "http://localhost:3000/accept-invitation").dispatch(
        make_invitation(email="ada@example.com")
    )

    request = sent[0]
    body = _json(request)
    assert str(request.url) == dispatchers.CLERK_INVITATIONS_URL
    assert request.headers["authorization"] == "Bearer sk_test_x"
    assert body["email_address"] == "ada@example.com"
    assert body["notify"] is True
    assert body["redirect_url"] == "http://localhost:3000/accept-invitation"


def test_it_ignores_an_existing_clerk_invitation(clerk):
    """Otherwise re-sending fails outright: Clerk refuses a second invitation for an address
    that already has one, and re-sending is exactly that case."""
    sent = clerk()
    ClerkInvitationDispatcher("sk_test_x").dispatch(make_invitation())
    assert _json(sent[0])["ignore_existing"] is True


def test_both_windows_say_the_same_thing(clerk):
    """Clerk's default is 30 days and ours is 7. Two expiry dates for one invitation is a
    support question waiting to happen."""
    sent = clerk()
    ClerkInvitationDispatcher("sk_test_x").dispatch(
        make_invitation(expires_at=datetime.now(UTC) + timedelta(days=7))
    )
    assert _json(sent[0])["expires_in_days"] in (6, 7)


def test_no_redirect_url_is_sent_when_none_is_configured(clerk):
    sent = clerk()
    ClerkInvitationDispatcher("sk_test_x").dispatch(make_invitation())
    assert "redirect_url" not in _json(sent[0])


# ------------------------------------------------------------------------- the answers


def test_a_refusal_is_reported_with_clerk_s_own_sentence(clerk):
    """The generic "delivery failed" is what an admin cannot act on; "that address is
    already a Clerk user" is what they can."""
    clerk(
        422,
        {"errors": [{"message": "duplicate", "long_message": "That email is already a user."}]},
    )

    with pytest.raises(InvitationDeliveryFailed) as raised:
        ClerkInvitationDispatcher("sk_test_x").dispatch(make_invitation())

    assert "That email is already a user." in str(raised.value)
    assert "422" in str(raised.value)


def test_a_refusal_with_no_readable_body_still_names_the_status(clerk):
    clerk(500, {})
    with pytest.raises(InvitationDeliveryFailed, match="500"):
        ClerkInvitationDispatcher("sk_test_x").dispatch(make_invitation())


def test_a_network_failure_is_reported_rather_than_raised_raw(monkeypatch):
    def explode(url, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(dispatchers.httpx, "post", explode)

    with pytest.raises(InvitationDeliveryFailed, match="could not reach Clerk"):
        ClerkInvitationDispatcher("sk_test_x").dispatch(make_invitation())


# --------------------------------------------------------------------- which adapter runs


def test_local_mode_delivers_nothing(monkeypatch):
    """The mode that exists so the whole flow runs with no accounts and no cloud
    (ADR-0008). Stated rather than inherited from whatever `.env` happens to say."""
    _as_mode(monkeypatch, auth_mode="local", secret_key="sk_test_x")
    assert isinstance(get_invitation_dispatcher(), LoggingInvitationDispatcher)


def test_clerk_mode_with_a_secret_key_talks_to_clerk(monkeypatch):
    _as_clerk(monkeypatch, secret_key="sk_test_x")
    assert isinstance(get_invitation_dispatcher(), ClerkInvitationDispatcher)


def test_clerk_mode_without_a_secret_key_falls_back_rather_than_failing(monkeypatch, caplog):
    """The roster still works; the missing key is named where somebody asking "why did
    nobody get an email" will find it."""
    _as_clerk(monkeypatch, secret_key="")

    with caplog.at_level("WARNING"):
        dispatcher = get_invitation_dispatcher()

    assert isinstance(dispatcher, LoggingInvitationDispatcher)
    assert "CLERK_SECRET_KEY" in caplog.text


# ---------------------------------------------------------------------------- helpers


def _json(request: httpx.Request) -> dict:
    import json

    return json.loads(request.content)


def _as_mode(monkeypatch, auth_mode: str, secret_key: str) -> None:
    """Read the settings as a process in that mode would, without rebuilding the app."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        dispatchers,
        "get_settings",
        lambda: settings.model_copy(
            update={"auth_mode": auth_mode, "clerk_secret_key": secret_key}
        ),
    )


def _as_clerk(monkeypatch, secret_key: str) -> None:
    _as_mode(monkeypatch, auth_mode="clerk", secret_key=secret_key)


def test_the_link_lands_on_a_page_that_can_sign_somebody_up():
    """Not `/sign-in`. An invited person has no account yet, so Clerk hands the ticket over
    as a sign-up and the sign-in form cannot complete it — it renders and spins for ever."""
    from app.config import get_settings

    derived = (
        get_settings()
        .model_copy(update={"allowed_origins": "http://localhost:3000"})
        .invitation_redirect_url
    )

    assert derived == "http://localhost:3000/accept-invitation"


def test_an_explicit_redirect_url_wins_over_the_derived_one():
    from app.config import get_settings

    settings = get_settings().model_copy(
        update={"clerk_invitation_redirect_url": "https://evals.example.com/welcome"}
    )

    assert settings.invitation_redirect_url == "https://evals.example.com/welcome"
