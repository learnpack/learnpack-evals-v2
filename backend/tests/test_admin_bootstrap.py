"""ADMIN_EMAILS: bootstrap allowlist, not an authorisation source (ADR-0007).

Applies only when an assessor is created. The security property being protected is that
logging in can never change an existing assessor's role.
"""

from uuid import UUID

import pytest

from app.modules.identity.application.resolve_assessor import ClerkIdentity, ResolveAssessor
from app.modules.identity.domain.assessor import Assessor, Role
from app.shared.domain.ids import new_id


class FakeAssessorRepository:
    def __init__(self, existing: list[Assessor] | None = None) -> None:
        self.assessors = {a.clerk_user_id: a for a in (existing or [])}
        self.updated: list[Assessor] = []

    def get_by_clerk_user_id(self, clerk_user_id: str) -> Assessor | None:
        return self.assessors.get(clerk_user_id)

    def get_by_id(self, assessor_id: UUID) -> Assessor | None:
        return next((a for a in self.assessors.values() if a.id == assessor_id), None)

    def get_by_email(self, email: str) -> Assessor | None:
        return next((a for a in self.assessors.values() if a.email == email), None)

    def list_by_ids(self, assessor_ids: list[UUID]) -> list[Assessor]:
        return [a for a in self.assessors.values() if a.id in assessor_ids]

    def add(self, assessor: Assessor) -> None:
        self.assessors[assessor.clerk_user_id] = assessor

    def update(self, assessor: Assessor) -> None:
        self.updated.append(assessor)


class FakeUow:
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class FakeInvitationRepository:
    """No invitations at all — these tests are about the allowlist, which is precisely the
    default that applies to whoever arrives without one (ADR-0049)."""

    def __init__(self, pending: list | None = None) -> None:
        self.pending = pending or []
        self.updated: list = []

    def find_pending_by_email(self, email: str):
        return next((i for i in self.pending if i.email == email.strip().lower()), None)

    def update(self, invitation) -> None:
        self.updated.append(invitation)


class FakePublisher:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


def resolve(repository, *, allowlist=(), invitations=None, **claims):
    use_case = ResolveAssessor(
        repository,
        invitations if invitations is not None else FakeInvitationRepository(),
        FakePublisher(),
        FakeUow(),
        bootstrap_admins=allowlist,
    )
    return use_case(
        ClerkIdentity(
            clerk_user_id=claims.get("clerk_user_id", "user_1"),
            email=claims.get("email"),
            display_name=claims.get("name", "Someone"),
            email_verified=claims.get("email_verified", True),
        )
    )


def existing(email: str, role: Role) -> Assessor:
    return Assessor(id=new_id(), clerk_user_id="user_1", email=email, display_name="Ada", role=role)


def test_a_listed_email_is_created_as_admin():
    repository = FakeAssessorRepository()
    result = resolve(repository, allowlist=["boss@acme.com"], email="boss@acme.com")
    assert result.role == "admin"


def test_an_unlisted_email_is_created_as_evaluator():
    repository = FakeAssessorRepository()
    result = resolve(repository, allowlist=["boss@acme.com"], email="sme@acme.com")
    assert result.role == "evaluator"


def test_matching_is_case_and_whitespace_insensitive():
    repository = FakeAssessorRepository()
    result = resolve(repository, allowlist=[" Boss@Acme.com "], email="boss@ACME.com")
    assert result.role == "admin"


def test_no_email_claim_falls_back_to_evaluator():
    """A missing Clerk JWT template must degrade safely, never grant admin."""
    repository = FakeAssessorRepository()
    result = resolve(repository, allowlist=["boss@acme.com"], email=None)
    assert result.role == "evaluator"


def test_empty_allowlist_creates_evaluators():
    repository = FakeAssessorRepository()
    assert resolve(repository, email="anyone@acme.com").role == "evaluator"


def test_adding_an_existing_evaluator_to_the_allowlist_does_not_promote_them():
    """The security property: logging in cannot escalate privileges.

    The allowlist is a creation default, not a permission. Promoting an existing assessor
    is `app.cli set-role` and nothing else.
    """
    repository = FakeAssessorRepository([existing("sme@acme.com", Role.EVALUATOR)])
    result = resolve(repository, allowlist=["sme@acme.com"], email="sme@acme.com")
    assert result.role == "evaluator"


def test_removing_an_admin_from_the_allowlist_does_not_demote_them():
    """`assessors.role` is the source of truth once the row exists."""
    repository = FakeAssessorRepository([existing("boss@acme.com", Role.ADMIN)])
    result = resolve(repository, allowlist=[], email="boss@acme.com")
    assert result.role == "admin"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.EVALUATOR])
def test_a_profile_refresh_never_touches_the_role(role):
    repository = FakeAssessorRepository([existing("someone@acme.com", role)])
    result = resolve(
        repository, allowlist=["someone@acme.com"], email="someone@acme.com", name="New Name"
    )
    assert result.role == str(role)
    assert result.display_name == "New Name"
