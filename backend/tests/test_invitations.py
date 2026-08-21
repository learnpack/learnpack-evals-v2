"""The `Invitation` aggregate: what an admin's act allows and refuses (ADR-0049).

Pure domain — no database. The property under test throughout is that an invitation grants
nothing by existing: it is a fact a *single* first login may consume, once, in time.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.identity.domain.assessor import Role
from app.modules.identity.domain.invitation import (
    DEFAULT_VALIDITY,
    InvalidInvitation,
    InvalidInvitationTransition,
    Invitation,
    InvitationStatus,
    normalize_email,
)
from app.shared.domain.ids import new_id

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def make_invitation(**overrides) -> Invitation:
    defaults = {
        "id": new_id(),
        "email": "ada@example.com",
        "expires_at": NOW + DEFAULT_VALIDITY,
    }
    return Invitation(**(defaults | overrides))


# ----------------------------------------------------------------------------- shape


def test_defaults_to_evaluator():
    assert make_invitation().role is Role.EVALUATOR


@pytest.mark.parametrize(
    ("raw", "stored"),
    [("  Ada@Example.COM ", "ada@example.com"), ("ADA@EXAMPLE.COM", "ada@example.com")],
)
def test_the_address_is_normalized(raw, stored):
    """Case and whitespace are not part of an identity: an invitation that failed to
    redeem because somebody typed a capital would look exactly like one never sent."""
    assert make_invitation(email=raw).email == stored
    assert normalize_email(raw) == stored


@pytest.mark.parametrize("bad", ["", "   ", "not-an-address"])
def test_an_address_is_required_and_has_to_look_like_one(bad):
    with pytest.raises(InvalidInvitation):
        make_invitation(email=bad)


def test_an_expiry_is_required():
    """An invitation that never expires is a standing key to a roster nobody re-reads."""
    with pytest.raises(InvalidInvitation):
        make_invitation(expires_at=None)


def test_status_and_role_accept_the_raw_strings_from_the_database():
    invitation = make_invitation(status="revoked", role="admin")
    assert invitation.status is InvitationStatus.REVOKED
    assert invitation.role is Role.ADMIN


# ------------------------------------------------------------------------- expiry


def test_expiry_is_derived_from_the_clock_not_from_the_status():
    invitation = make_invitation(expires_at=NOW - timedelta(seconds=1))
    assert invitation.status is InvitationStatus.PENDING
    assert invitation.is_expired(NOW)
    assert not invitation.is_redeemable(NOW)


def test_a_fresh_invitation_is_redeemable():
    assert make_invitation().is_redeemable(NOW)


# ------------------------------------------------------------------------ redeeming


def test_redeeming_names_the_assessor_it_produced():
    invitation = make_invitation()
    assessor_id = new_id()

    invitation.redeem(assessor_id, NOW)

    assert invitation.status is InvitationStatus.ACCEPTED
    assert invitation.accepted_by == assessor_id


def test_an_invitation_is_redeemed_only_once():
    """A second redemption would mean two credentials answered to one invitation, and the
    second has no claim on the role it was granting."""
    invitation = make_invitation()
    invitation.redeem(new_id(), NOW)

    with pytest.raises(InvalidInvitationTransition):
        invitation.redeem(new_id(), NOW)


def test_an_expired_invitation_cannot_be_redeemed():
    invitation = make_invitation(expires_at=NOW - timedelta(days=1))
    with pytest.raises(InvalidInvitationTransition):
        invitation.redeem(new_id(), NOW)


def test_a_revoked_invitation_cannot_be_redeemed():
    invitation = make_invitation()
    invitation.revoke()
    with pytest.raises(InvalidInvitationTransition):
        invitation.redeem(new_id(), NOW)


# ------------------------------------------------------------------ revoke / re-send


def test_revoking_is_idempotent():
    invitation = make_invitation()
    invitation.revoke()
    invitation.revoke()
    assert invitation.status is InvitationStatus.REVOKED


def test_an_accepted_invitation_cannot_be_revoked():
    """The assessor exists; withdrawing the invitation would change nothing and would
    read as if it had."""
    invitation = make_invitation()
    invitation.redeem(new_id(), NOW)
    with pytest.raises(InvalidInvitationTransition):
        invitation.revoke()


def test_re_sending_reopens_the_window_of_an_expired_invitation():
    invitation = make_invitation(expires_at=NOW - timedelta(days=1))
    invitation.extend(now=NOW)
    assert invitation.is_redeemable(NOW)


def test_only_a_pending_invitation_can_be_re_sent():
    invitation = make_invitation()
    invitation.redeem(new_id(), NOW)
    with pytest.raises(InvalidInvitationTransition):
        invitation.extend(now=NOW)
