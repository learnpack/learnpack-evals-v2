"""Registering a human evaluator, end to end (ADR-0049).

The act under test spans two moments that are deliberately far apart: an admin invites, and
some time later a login turns that into an `Assessor`. What each test pins down is that the
second moment carries exactly what the first one decided — and that nothing else can make it
happen.
"""

import pytest
from sqlalchemy import text


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def invite(admin, cleanup, unique):
    """Send an invitation and register it for cleanup. Returns the response body."""

    def _invite(label: str = "ada", **overrides):
        body = {"email": f"{label}-{unique}@example.com"} | overrides
        response = admin.post("/admin/invitations", json=body)
        assert response.status_code == 201, response.text
        created = response.json()
        cleanup["invitations"].append(created["invitation_id"])
        return created

    return _invite


def sign_in(as_user, cleanup, email: str, *, subject: str, email_verified: bool = True):
    """A first login for `email`, which is the only moment an invitation is consumed."""
    client = as_user(subject, email, "Someone", email_verified)
    me = client.get("/me")
    assert me.status_code == 200, me.text
    cleanup["assessors"].append(me.json()["assessor_id"])
    return client, me.json()


# ---------------------------------------------------------------------------- the act


def test_inviting_creates_no_account(invite, admin):
    """The whole point of the model: the act registers an intention, not a principal."""
    created = invite(role="admin")

    assert created["status"] == "pending"
    assert created["expired"] is False
    # The response carries the same timestamp the list will show, not a null the first
    # refetch quietly replaces.
    assert created["created_at"] is not None
    emails = [a["email"] for a in admin.get("/admin/assessors").json()]
    assert created["email"] not in emails


def test_the_first_login_carries_the_role_and_the_expertise_that_were_declared(
    invite, as_user, cleanup, admin, unique
):
    created = invite(role="admin", display_name="Ada Lovelace", expertise="Instructional design")

    _, me = sign_in(as_user, cleanup, created["email"], subject=f"user_invited_{unique}")

    assert me["role"] == "admin"
    listed = next(a for a in admin.get("/admin/assessors").json() if a["email"] == created["email"])
    assert listed["role"] == "admin"
    # Nothing wrote `expertise` before invitations existed, and nothing read it back until
    # the roster published it. Asserted through the endpoint, so both halves are covered.
    assert listed["expertise"] == "Instructional design"


def test_redeeming_marks_the_invitation_accepted_and_names_the_assessor(
    invite, as_user, cleanup, admin, unique
):
    created = invite()

    _, me = sign_in(as_user, cleanup, created["email"], subject=f"user_ok_{unique}")

    after = _invitation(admin, created["invitation_id"])
    assert after["status"] == "accepted"
    assert after["accepted_by"] == me["assessor_id"]


def test_the_display_name_the_provider_sends_wins_over_the_one_that_was_typed(
    invite, as_user, cleanup, admin, unique
):
    """The admin's guess fills a gap; it does not overwrite what the person is called."""
    created = invite(display_name="A. Lovelace")

    sign_in(as_user, cleanup, created["email"], subject=f"user_name_{unique}")

    listed = next(a for a in admin.get("/admin/assessors").json() if a["email"] == created["email"])
    assert listed["display_name"] == "Someone"


# ------------------------------------------------------------------- what cannot redeem


def test_an_unverified_address_does_not_redeem(invite, as_user, cleanup, admin, unique):
    """Matching an invitation on an address nobody vouched for is how somebody else's
    invitation gets accepted. The login still works — it just gets the default role."""
    created = invite(role="admin")

    _, me = sign_in(
        as_user, cleanup, created["email"], subject=f"user_unv_{unique}", email_verified=False
    )

    assert me["role"] == "evaluator"
    assert _invitation(admin, created["invitation_id"])["status"] == "pending"


def test_a_revoked_invitation_does_not_redeem(invite, as_user, cleanup, admin, unique):
    created = invite(role="admin")
    admin.post(f"/admin/invitations/{created['invitation_id']}/revoke")

    _, me = sign_in(as_user, cleanup, created["email"], subject=f"user_rev_{unique}")

    assert me["role"] == "evaluator"
    assert _invitation(admin, created["invitation_id"])["status"] == "revoked"


def test_an_expired_invitation_does_not_redeem(invite, as_user, cleanup, admin, session, unique):
    created = invite(role="admin")
    _expire(session, created["invitation_id"])

    _, me = sign_in(as_user, cleanup, created["email"], subject=f"user_exp_{unique}")

    assert me["role"] == "evaluator"
    # Still pending: expiry is derived, so nothing rewrote the row.
    listed = _invitation(admin, created["invitation_id"])
    assert (listed["status"], listed["expired"]) == ("pending", True)


def test_a_second_login_does_not_redeem_anything(invite, as_user, cleanup, admin, unique):
    """An invitation reaches an assessor that does not exist yet, or it does not reach one
    at all — otherwise a login could escalate a privilege (ADR-0007's invariant)."""
    email = f"already-{unique}@example.com"
    client, me = sign_in(as_user, cleanup, email, subject=f"user_twice_{unique}")

    # Inviting an address that already signed in is refused at the door...
    refused = admin.post("/admin/invitations", json={"email": email, "role": "admin"})
    assert refused.status_code == 409

    assert client.get("/me").json()["role"] == "evaluator"
    assert me["role"] == "evaluator"


# ------------------------------------------------------------------------ the refusals


def test_two_pending_invitations_for_one_address_are_refused(invite, admin, unique):
    created = invite()
    again = admin.post("/admin/invitations", json={"email": created["email"]})

    assert again.status_code == 409
    assert "re-send" in again.json()["detail"]


def test_revoking_frees_the_address_to_be_invited_again(invite, admin, cleanup):
    created = invite()
    admin.post(f"/admin/invitations/{created['invitation_id']}/revoke")

    again = admin.post("/admin/invitations", json={"email": created["email"]})

    assert again.status_code == 201
    cleanup["invitations"].append(again.json()["invitation_id"])


def test_re_sending_reopens_a_window_that_closed(invite, admin, session):
    created = invite()
    _expire(session, created["invitation_id"])
    assert _invitation(admin, created["invitation_id"])["expired"] is True

    resent = admin.post(f"/admin/invitations/{created['invitation_id']}/resend")

    assert resent.status_code == 200
    assert resent.json()["expired"] is False


def test_an_accepted_invitation_cannot_be_revoked(invite, as_user, cleanup, admin, unique):
    created = invite()
    sign_in(as_user, cleanup, created["email"], subject=f"user_acc_{unique}")

    refused = admin.post(f"/admin/invitations/{created['invitation_id']}/revoke")

    assert refused.status_code == 409


def test_an_unknown_role_is_refused(admin, unique):
    response = admin.post(
        "/admin/invitations", json={"email": f"x-{unique}@example.com", "role": "owner"}
    )
    assert response.status_code == 422


def test_an_address_that_is_not_one_is_refused(admin):
    response = admin.post("/admin/invitations", json={"email": "not-an-address"})
    assert response.status_code == 422


def test_inviting_requires_admin(as_user, cleanup, unique):
    client, _ = sign_in(
        as_user, cleanup, f"plain-{unique}@example.com", subject=f"user_plain_{unique}"
    )

    assert client.post("/admin/invitations", json={"email": "x@example.com"}).status_code == 403
    assert client.get("/admin/invitations").status_code == 403


# ---------------------------------------------------------------------------- helpers


def _invitation(admin, invitation_id: str) -> dict:
    listed = admin.get("/admin/invitations")
    assert listed.status_code == 200, listed.text
    return next(i for i in listed.json() if i["invitation_id"] == invitation_id)


def _expire(session, invitation_id: str) -> None:
    """Move the window into the past. Nothing else changes — that is what makes `expired`
    derived rather than a status somebody has to remember to write."""
    session.execute(
        text(
            "UPDATE assessor_invitations SET expires_at = now() - interval '1 day' WHERE id = :id"
        ),
        {"id": invitation_id},
    )
    session.commit()
