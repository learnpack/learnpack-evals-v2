"""An assessor leaves without being erased (ADR-0051).

Two things have to be true at once, and they pull in opposite directions: everything the
person produced survives untouched, and the person themselves is out — no new work, no way
in. A test that only checked the first would pass over a purely cosmetic offboarding.
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


def deactivate(admin, assessor_id: str):
    return admin.post(f"/admin/assessors/{assessor_id}/active", json={"active": False})


# ------------------------------------------------------------------------------ the act


def test_a_deactivated_assessor_does_not_get_through_the_door(admin, evaluator):
    """The half that makes offboarding real. Removing somebody from pickers while their
    credential still works is a list, not a departure."""
    client, assessor_id = evaluator

    assert deactivate(admin, assessor_id).status_code == 200

    assert client.get("/me").status_code == 403
    assert client.get("/me/assignments").status_code == 403


def test_they_stay_in_the_roster_and_say_they_left(admin, evaluator):
    _, assessor_id = evaluator
    deactivate(admin, assessor_id)

    listed = next(
        a for a in admin.get("/admin/assessors").json() if a["assessor_id"] == assessor_id
    )
    assert listed["status"] == "deactivated"


def test_what_they_produced_is_untouched(admin, evaluator, session):
    """The reason this is a state and not a delete: an assessor is the key of provenance,
    and their evaluations record what happened (the argument ADR-0033 makes for content)."""
    _, assessor_id = evaluator
    before = _evaluations_of(session, assessor_id)

    deactivate(admin, assessor_id)

    assert _evaluations_of(session, assessor_id) == before
    assert _row_exists(session, assessor_id)


def test_coming_back_restores_access(admin, evaluator):
    client, assessor_id = evaluator
    deactivate(admin, assessor_id)

    response = admin.post(f"/admin/assessors/{assessor_id}/active", json={"active": True})

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert client.get("/me").status_code == 200


def test_deactivating_records_who_decided(admin, evaluator, session):
    _, assessor_id = evaluator
    deactivate(admin, assessor_id)

    payload = (
        session.execute(
            text(
                "SELECT payload FROM events WHERE event_type = 'AssessorDeactivated' "
                "AND aggregate_id = :id"
            ),
            {"id": assessor_id},
        )
        .mappings()
        .one()
    )["payload"]

    assert payload["changedBy"] == admin.get("/me").json()["assessor_id"]


def test_deactivating_somebody_already_out_is_not_an_event(admin, evaluator, session):
    _, assessor_id = evaluator
    deactivate(admin, assessor_id)
    before = _lifecycle_events(session, assessor_id)

    assert deactivate(admin, assessor_id).status_code == 200

    assert _lifecycle_events(session, assessor_id) == before


# --------------------------------------------------------------------------- the refusals


def test_nobody_deactivates_themselves(admin):
    me = admin.get("/me").json()["assessor_id"]

    response = deactivate(admin, me)

    assert response.status_code == 409
    assert admin.get("/me").status_code == 200


def test_an_automated_assessor_is_not_withdrawn_from_here(admin, cleanup, session, unique):
    assessor_id = _register_automated(session, cleanup, unique)

    response = deactivate(admin, assessor_id)

    assert response.status_code == 409
    assert "in code" in response.json()["detail"]


def test_an_unknown_assessor_is_a_404(admin):
    response = deactivate(admin, "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_deactivating_requires_admin(evaluator, admin):
    client, _ = evaluator
    target = admin.get("/me").json()["assessor_id"]

    assert deactivate(client, target).status_code == 403


# ------------------------------------------------------------- the last admin, in isolation
#
# Over a fake repository, for the reason ADR-0050's guard is: `count_admins()` reads the
# whole store and the suite shares one.


class FakeAssessorRepository:
    def __init__(self, assessors) -> None:
        self.assessors = {a.id: a for a in assessors}
        self.updated: list = []

    def get_by_id(self, assessor_id):
        return self.assessors.get(assessor_id)

    def count_admins(self) -> int:
        return sum(1 for a in self.assessors.values() if a.is_admin and a.is_active)

    def update(self, assessor) -> None:
        self.updated.append(assessor)


class FakePublisher:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class FakeUow:
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _human(role: str = "evaluator"):
    from app.modules.identity.domain.assessor import Assessor
    from app.shared.domain.ids import new_id

    return Assessor(id=new_id(), clerk_user_id=f"user_{new_id()}", role=role)


def _set_active(repository, target, actor, active: bool):
    from app.modules.identity.application.deactivate_assessor import (
        SetAssessorActive,
        SetAssessorActiveCommand,
    )

    use_case = SetAssessorActive(repository, FakePublisher(), FakeUow())
    return use_case(
        SetAssessorActiveCommand(assessor_id=target.id, active=active, changed_by=actor.id)
    )


def test_the_last_admin_cannot_be_deactivated():
    from app.modules.identity.application.deactivate_assessor import CannotDeactivateLastAdmin

    only_admin, actor = _human("admin"), _human("admin")
    repository = FakeAssessorRepository([only_admin])

    with pytest.raises(CannotDeactivateLastAdmin):
        _set_active(repository, only_admin, actor, active=False)

    assert only_admin.is_active
    assert repository.updated == []


def test_one_of_two_admins_can_be_deactivated():
    target, other, actor = _human("admin"), _human("admin"), _human("admin")
    repository = FakeAssessorRepository([target, other])

    _set_active(repository, target, actor, active=False)

    assert not target.is_active


def test_a_deactivated_admin_no_longer_counts_as_one():
    """Otherwise the guard would protect a door nobody can open: an admin who left is not
    somebody who can grant the role back."""
    left, remaining, actor = _human("admin"), _human("admin"), _human("admin")
    repository = FakeAssessorRepository([left, remaining])
    _set_active(repository, left, actor, active=False)

    from app.modules.identity.application.deactivate_assessor import CannotDeactivateLastAdmin

    with pytest.raises(CannotDeactivateLastAdmin):
        _set_active(repository, remaining, actor, active=False)


# ---------------------------------------------------------------------------- helpers


def _lifecycle_events(session, assessor_id: str) -> int:
    return int(
        session.execute(
            text(
                "SELECT count(*) FROM events WHERE aggregate_id = :id AND event_type IN "
                "('AssessorDeactivated', 'AssessorReactivated')"
            ),
            {"id": assessor_id},
        ).scalar_one()
    )


def _evaluations_of(session, assessor_id: str) -> int:
    return int(
        session.execute(
            text("SELECT count(*) FROM evaluations WHERE assessor_id = :id"), {"id": assessor_id}
        ).scalar_one()
    )


def _row_exists(session, assessor_id: str) -> bool:
    return (
        session.execute(
            text("SELECT count(*) FROM assessors WHERE id = :id"), {"id": assessor_id}
        ).scalar_one()
        == 1
    )


def _register_automated(session, cleanup, unique: str) -> str:
    from app.modules.identity.domain.assessor import Assessor, Kind
    from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
    from app.shared.domain.ids import new_id

    assessor = Assessor(
        id=new_id(),
        clerk_user_id=None,
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
