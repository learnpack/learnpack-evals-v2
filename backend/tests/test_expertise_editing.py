"""Correcting an expertise profile.

Declared once, when the invitation is written (ADR-0049). It goes stale the ordinary way, and
everybody who signed in before invitations existed has none at all — so it has to be
correctable. What these tests pin down is that it is a *description*, not a grant: it carries
none of the guardrails a role or a deactivation does.
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
def evaluator(as_user, cleanup, unique):
    client = as_user(f"user_ev_{unique}", f"ev-{unique}@example.com", "Ev")
    assessor_id = client.get("/me").json()["assessor_id"]
    cleanup["assessors"].append(assessor_id)
    return client, assessor_id


def set_expertise(admin, assessor_id: str, expertise):
    return admin.patch(f"/admin/assessors/{assessor_id}/expertise", json={"expertise": expertise})


def expertise_of(admin, assessor_id: str):
    return next(a for a in admin.get("/admin/assessors").json() if a["assessor_id"] == assessor_id)[
        "expertise"
    ]


# ------------------------------------------------------------------------------ the act


def test_an_expertise_profile_can_be_written_where_there_was_none(admin, evaluator):
    """The case that motivates this: somebody who signed in before invitations existed."""
    _, assessor_id = evaluator
    assert expertise_of(admin, assessor_id) is None

    response = set_expertise(admin, assessor_id, "Instructional design")

    assert response.status_code == 200
    assert response.json()["expertise"] == "Instructional design"
    assert expertise_of(admin, assessor_id) == "Instructional design"


def test_it_can_be_corrected(admin, evaluator):
    _, assessor_id = evaluator
    set_expertise(admin, assessor_id, "Python")

    set_expertise(admin, assessor_id, "Python · K-12 maths")

    assert expertise_of(admin, assessor_id) == "Python · K-12 maths"


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_clears_it(admin, evaluator, blank):
    """An empty box and a box nobody filled say the same thing."""
    _, assessor_id = evaluator
    set_expertise(admin, assessor_id, "Python")

    assert set_expertise(admin, assessor_id, blank).status_code == 200
    assert expertise_of(admin, assessor_id) is None


def test_surrounding_whitespace_is_not_part_of_it(admin, evaluator):
    _, assessor_id = evaluator
    set_expertise(admin, assessor_id, "  Instructional design  ")
    assert expertise_of(admin, assessor_id) == "Instructional design"


def test_it_records_who_said_it(admin, evaluator, session):
    _, assessor_id = evaluator
    set_expertise(admin, assessor_id, "Assessment literacy")

    payload = (
        session.execute(
            text(
                "SELECT payload FROM events WHERE event_type = 'AssessorExpertiseChanged' "
                "AND aggregate_id = :id"
            ),
            {"id": assessor_id},
        )
        .mappings()
        .one()
    )["payload"]

    assert payload["expertise"] == "Assessment literacy"
    assert payload["changedBy"] == admin.get("/me").json()["assessor_id"]


def test_writing_the_same_profile_again_is_not_an_event(admin, evaluator, session):
    _, assessor_id = evaluator
    set_expertise(admin, assessor_id, "Python")
    before = _expertise_events(session, assessor_id)

    assert set_expertise(admin, assessor_id, "Python").status_code == 200

    assert _expertise_events(session, assessor_id) == before


# ----------------------------------------------------------- a description, not a grant


def test_you_may_correct_your_own(admin):
    """Unlike a role: saying what you work on grants you nothing."""
    me = admin.get("/me").json()["assessor_id"]

    response = set_expertise(admin, me, "Evaluation design")

    assert response.status_code == 200
    assert expertise_of(admin, me) == "Evaluation design"


def test_a_deactivated_assessor_can_still_be_corrected(admin, evaluator):
    """Their record stays readable (ADR-0051), so it stays worth keeping truthful."""
    _, assessor_id = evaluator
    admin.post(f"/admin/assessors/{assessor_id}/active", json={"active": False})

    assert set_expertise(admin, assessor_id, "Former SME - Python").status_code == 200


def test_the_last_admin_is_not_protected_from_this(admin):
    """No guardrail applies: nothing here can lock anybody out."""
    me = admin.get("/me").json()["assessor_id"]
    assert set_expertise(admin, me, None).status_code == 200


# --------------------------------------------------------------------------- the refusals


def test_an_automated_assessor_has_no_expertise_profile(admin, cleanup, session, unique):
    assessor_id = _register_automated(session, cleanup, unique)

    response = set_expertise(admin, assessor_id, "anything")

    assert response.status_code == 409
    assert "coverage" in response.json()["detail"]


def test_an_unknown_assessor_is_a_404(admin):
    assert set_expertise(admin, "00000000-0000-0000-0000-000000000000", "x").status_code == 404


def test_correcting_requires_admin(evaluator):
    client, assessor_id = evaluator
    assert set_expertise(client, assessor_id, "x").status_code == 403


# ---------------------------------------------------------------------------- helpers


def _expertise_events(session, assessor_id: str) -> int:
    return int(
        session.execute(
            text(
                "SELECT count(*) FROM events WHERE event_type = 'AssessorExpertiseChanged' "
                "AND aggregate_id = :id"
            ),
            {"id": assessor_id},
        ).scalar_one()
    )


def _register_automated(session, cleanup, unique: str) -> str:
    from app.modules.identity.domain.assessor import Assessor, Kind
    from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
    from app.shared.domain.ids import new_id

    assessor = Assessor(
        id=new_id(),
        display_name=f"bot-{unique}",
        kind=Kind.AUTOMATED,
        source_config={
            "name": f"bot-{unique}",
            "version": "1",
            "instrumentId": "learnpack-pedagogical",
        },
    )
    SqlAlchemyAssessorRepository(session).add(assessor)
    session.commit()
    cleanup["assessors"].append(assessor.id)
    return str(assessor.id)
