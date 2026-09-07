"""Writing the instance's JWT template (ADR-0004, ADR-0007).

No network and no Clerk account: `httpx.MockTransport` answers as Clerk would, so what is
pinned down is the request we send and what we make of each answer. What matters most here is
the shape of the decision — create, update, or leave alone — because this command is run again
after every change to an environment, and one that created a second template every time would
be worse than the dashboard step it replaces.
"""

import json

import httpx
import pytest

from app.cli import run_setup_clerk_jwt_template
from app.config import get_settings
from app.platform import clerk_instance
from app.platform.clerk_instance import (
    CLAIMS,
    JWT_TEMPLATES_URL,
    TEMPLATE_NAME,
    ClerkSetupFailed,
    ensure_jwt_template,
)

OTHER_CLAIMS = {"email": "{{user.primary_email_address}}"}


@pytest.fixture
def clerk(monkeypatch):
    """A Clerk that records what it was asked and answers what the test scripted.

    `httpx.request` is module-level in the adapter, so it is patched with a client bound to a
    mock transport — the requests are built for real and never leave the process.
    """
    sent: list[httpx.Request] = []

    def _clerk(*answers: tuple[int, object]):
        remaining = list(answers)

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            status, body = remaining.pop(0)
            return httpx.Response(status, json=body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(
            clerk_instance.httpx,
            "request",
            lambda method, url, **kwargs: client.request(method, url, **kwargs),
        )
        return sent

    return _clerk


def test_creates_the_template_when_the_instance_carries_none(clerk):
    sent = clerk((200, []), (200, {"id": "jtmp_1", "name": TEMPLATE_NAME, "claims": CLAIMS}))

    outcome = ensure_jwt_template("sk_test_x")

    assert (outcome.action, outcome.template_id) == ("created", "jtmp_1")
    listing, creation = sent
    assert (listing.method, str(listing.url)) == ("GET", JWT_TEMPLATES_URL)
    assert (creation.method, str(creation.url)) == ("POST", JWT_TEMPLATES_URL)
    assert creation.headers["Authorization"] == "Bearer sk_test_x"


def test_the_created_template_carries_the_three_claims_the_backend_reads(clerk):
    """The shortcodes, verbatim. `email_verified` has several plausible spellings and gates
    redeeming an invitation (ADR-0049), which fails quietly when it is wrong."""
    sent = clerk((200, []), (200, {"id": "jtmp_1"}))

    ensure_jwt_template("sk_test_x")

    assert json.loads(sent[1].content)["claims"] == {
        "email": "{{user.primary_email_address}}",
        "name": "{{user.full_name}}",
        "email_verified": "{{user.email_verified}}",
    }


def test_updates_a_template_whose_claims_drifted(clerk):
    sent = clerk(
        (200, [{"id": "jtmp_1", "name": TEMPLATE_NAME, "claims": OTHER_CLAIMS}]),
        (200, {"id": "jtmp_1"}),
    )

    outcome = ensure_jwt_template("sk_test_x")

    assert outcome.action == "updated"
    assert (sent[1].method, str(sent[1].url)) == ("PATCH", f"{JWT_TEMPLATES_URL}/jtmp_1")


def test_leaves_a_template_that_already_says_what_it_should(clerk):
    """Idempotent, and it says so: the command is part of a runbook that gets re-run."""
    sent = clerk((200, [{"id": "jtmp_1", "name": TEMPLATE_NAME, "claims": CLAIMS}]))

    outcome = ensure_jwt_template("sk_test_x")

    assert (outcome.action, outcome.template_id) == ("unchanged", "jtmp_1")
    assert len(sent) == 1, "nothing is written when nothing has to change"


def test_a_template_of_another_name_is_not_this_one(clerk):
    """The name is the handle: it is what the frontend asks for a token by."""
    sent = clerk(
        (200, [{"id": "jtmp_other", "name": "something-else", "claims": CLAIMS}]),
        (200, {"id": "jtmp_1"}),
    )

    assert ensure_jwt_template("sk_test_x").action == "created"
    assert sent[1].method == "POST"


def test_reads_a_listing_wrapped_in_data(clerk):
    """Clerk answers some listings bare and some wrapped, and reading the wrong one would find
    no template and mint a second."""
    clerk((200, {"data": [{"id": "jtmp_1", "name": TEMPLATE_NAME, "claims": CLAIMS}]}))

    assert ensure_jwt_template("sk_test_x").action == "unchanged"


def test_a_refusal_carries_clerks_own_sentence(clerk):
    clerk((403, {"errors": [{"long_message": "The secret key does not permit this."}]}))

    with pytest.raises(ClerkSetupFailed) as raised:
        ensure_jwt_template("sk_test_x")

    assert "The secret key does not permit this." in str(raised.value)
    assert "403" in str(raised.value)


def test_an_unreachable_clerk_is_named_as_such(monkeypatch):
    """A different failure from a refusal, and the remedy is a different one too."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        clerk_instance.httpx,
        "request",
        lambda method, url, **kwargs: client.request(method, url, **kwargs),
    )

    with pytest.raises(ClerkSetupFailed) as raised:
        ensure_jwt_template("sk_test_x")

    assert "could not reach Clerk" in str(raised.value)


def test_the_command_refuses_without_a_secret_key(monkeypatch, capsys):
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    get_settings.cache_clear()
    try:
        assert run_setup_clerk_jwt_template(TEMPLATE_NAME) == 1
    finally:
        get_settings.cache_clear()

    assert "CLERK_SECRET_KEY is not set" in capsys.readouterr().err


def test_the_command_reports_what_it_did(clerk, monkeypatch, capsys):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    get_settings.cache_clear()
    clerk((200, [{"id": "jtmp_1", "name": TEMPLATE_NAME, "claims": CLAIMS}]))
    try:
        assert run_setup_clerk_jwt_template(TEMPLATE_NAME) == 0
    finally:
        get_settings.cache_clear()

    assert "unchanged" in capsys.readouterr().out
