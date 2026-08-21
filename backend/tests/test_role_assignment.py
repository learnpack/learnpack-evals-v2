"""Granting a role from the console (ADR-0050).

The property being protected is still ADR-0007's: **authenticating cannot escalate a
privilege**. These tests are about the other half — an admin doing it deliberately, and the
two ways that goes wrong badly enough to deserve a refusal rather than a warning.
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
def second_admin(as_user, cleanup, promote, unique):
    """A second admin, so demoting the first is not the last-admin case."""
    email = f"admin2-{unique}@example.com"
    client = as_user(f"user_admin2_{unique}", email, "Admin Two")
    assessor_id = client.get("/me").json()["assessor_id"]
    cleanup["assessors"].append(assessor_id)
    promote(email)
    return client, assessor_id


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    client = as_user(f"user_ev_{unique}", f"ev-{unique}@example.com", "Ev")
    assessor_id = client.get("/me").json()["assessor_id"]
    cleanup["assessors"].append(assessor_id)
    return client, assessor_id


def role_of(admin, assessor_id: str) -> str:
    return next(a for a in admin.get("/admin/assessors").json() if a["assessor_id"] == assessor_id)[
        "role"
    ]


# ------------------------------------------------------------------------- the happy act


def test_an_admin_promotes_an_evaluator(admin, evaluator):
    client, assessor_id = evaluator

    response = admin.patch(f"/admin/assessors/{assessor_id}", json={"role": "admin"})

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"
    # The role is read where authorisation reads it, not only where the console shows it.
    assert client.get("/me").json()["role"] == "admin"


def test_promoting_records_who_decided_and_what_changed(admin, evaluator, session):
    _, assessor_id = evaluator
    admin.patch(f"/admin/assessors/{assessor_id}", json={"role": "admin"})

    event = (
        session.execute(
            text(
                "SELECT payload FROM events WHERE event_type = 'AssessorRoleChanged' "
                "AND aggregate_id = :id"
            ),
            {"id": assessor_id},
        )
        .mappings()
        .one()
    )["payload"]

    assert (event["from"], event["to"]) == ("evaluator", "admin")
    assert event["changedBy"] == admin.get("/me").json()["assessor_id"]


def test_setting_the_role_somebody_already_has_is_not_an_event(admin, evaluator, session):
    """Nothing happened, so nothing is reported: a role change that changed no role would
    put a fact in the outbox that never occurred."""
    _, assessor_id = evaluator

    response = admin.patch(f"/admin/assessors/{assessor_id}", json={"role": "evaluator"})

    assert response.status_code == 200
    assert _role_events(session, assessor_id) == 0


def test_an_admin_demotes_another_admin(admin, second_admin):
    _, other_id = second_admin

    response = admin.patch(f"/admin/assessors/{other_id}", json={"role": "evaluator"})

    assert response.status_code == 200
    assert role_of(admin, other_id) == "evaluator"


# --------------------------------------------------------------------------- the refusals


def test_nobody_changes_their_own_role(admin):
    me = admin.get("/me").json()["assessor_id"]

    response = admin.patch(f"/admin/assessors/{me}", json={"role": "evaluator"})

    assert response.status_code == 409
    assert admin.get("/me").json()["role"] == "admin"


def test_an_automated_assessor_has_no_role_to_grant(admin, cleanup, session, unique):
    assessor_id = _register_automated(session, cleanup, unique)

    response = admin.patch(f"/admin/assessors/{assessor_id}", json={"role": "admin"})

    assert response.status_code == 409
    assert "ratification" in response.json()["detail"]


def test_an_unknown_role_is_refused(admin, evaluator):
    _, assessor_id = evaluator
    response = admin.patch(f"/admin/assessors/{assessor_id}", json={"role": "owner"})
    assert response.status_code == 422


def test_an_unknown_assessor_is_a_404(admin):
    response = admin.patch(
        "/admin/assessors/00000000-0000-0000-0000-000000000000", json={"role": "admin"}
    )
    assert response.status_code == 404


def test_changing_a_role_requires_admin(evaluator, second_admin):
    client, _ = evaluator
    _, target = second_admin

    assert client.patch(f"/admin/assessors/{target}", json={"role": "evaluator"}).status_code == 403


# -------------------------------------------------------------------- the last admin
#
# Over a fake repository rather than the API: `count_admins()` counts the whole store, and
# the suite shares one — "there is exactly one admin left" is a global fact no integration
# test can honestly arrange without demoting everybody else's fixtures.


class FakeAssessorRepository:
    def __init__(self, assessors) -> None:
        self.assessors = {a.id: a for a in assessors}
        self.updated: list = []

    def get_by_id(self, assessor_id):
        return self.assessors.get(assessor_id)

    def count_admins(self) -> int:
        return sum(1 for a in self.assessors.values() if a.is_admin)

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


def _human(role: str):
    from app.modules.identity.domain.assessor import Assessor
    from app.shared.domain.ids import new_id

    return Assessor(id=new_id(), clerk_user_id=f"user_{new_id()}", role=role)


def test_the_last_admin_cannot_be_demoted():
    from app.modules.identity.application.change_role import (
        CannotDemoteLastAdmin,
        ChangeAssessorRole,
        ChangeAssessorRoleCommand,
    )
    from app.modules.identity.domain.assessor import Role

    only_admin, actor = _human("admin"), _human("admin")
    # `actor` is the caller's id and is deliberately NOT in the store: what the guard reads
    # is how many admins exist, and here that is one.
    repository = FakeAssessorRepository([only_admin])
    use_case = ChangeAssessorRole(repository, FakePublisher(), FakeUow())

    with pytest.raises(CannotDemoteLastAdmin):
        use_case(
            ChangeAssessorRoleCommand(
                assessor_id=only_admin.id, role=Role.EVALUATOR, changed_by=actor.id
            )
        )
    assert only_admin.is_admin
    assert repository.updated == []


def test_one_of_two_admins_can_be_demoted():
    from app.modules.identity.application.change_role import (
        ChangeAssessorRole,
        ChangeAssessorRoleCommand,
    )
    from app.modules.identity.domain.assessor import Role

    target, other, actor = _human("admin"), _human("admin"), _human("admin")
    repository = FakeAssessorRepository([target, other])
    publisher = FakePublisher()
    use_case = ChangeAssessorRole(repository, publisher, FakeUow())

    use_case(
        ChangeAssessorRoleCommand(assessor_id=target.id, role=Role.EVALUATOR, changed_by=actor.id)
    )

    assert not target.is_admin
    assert [e.event_type for e in publisher.published] == ["AssessorRoleChanged"]


def test_promoting_is_never_blocked_by_the_last_admin_guard():
    """The guard is about losing the last admin, not about counting them: promoting when
    there is exactly one must not be refused."""
    from app.modules.identity.application.change_role import (
        ChangeAssessorRole,
        ChangeAssessorRoleCommand,
    )
    from app.modules.identity.domain.assessor import Role

    only_admin, target, actor = _human("admin"), _human("evaluator"), _human("admin")
    repository = FakeAssessorRepository([only_admin, target])
    use_case = ChangeAssessorRole(repository, FakePublisher(), FakeUow())

    use_case(ChangeAssessorRoleCommand(assessor_id=target.id, role=Role.ADMIN, changed_by=actor.id))

    assert target.is_admin


# ---------------------------------------------------------------------------- helpers


def _role_events(session, assessor_id: str) -> int:
    return int(
        session.execute(
            text(
                "SELECT count(*) FROM events WHERE event_type = 'AssessorRoleChanged' "
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
