"""Assessor invariants — pure domain, no DB."""

import pytest

from app.modules.identity.domain.assessor import Assessor, InvalidAssessor, Kind, Role
from app.shared.domain.ids import new_id


def make_assessor(**overrides) -> Assessor:
    return Assessor(**({"id": new_id(), "clerk_user_id": "user_abc"} | overrides))


def make_automated(**overrides) -> Assessor:
    base = {
        "id": new_id(),
        "clerk_user_id": None,
        "kind": "automated",
        "source_config": {
            "name": "structural",
            "version": "1",
            "instrumentId": "learnpack-course-qa",
        },
    }
    return Assessor(**(base | overrides))


def test_defaults_to_evaluator():
    assert make_assessor().role is Role.EVALUATOR
    assert not make_assessor().is_admin


def test_clerk_user_id_is_required():
    with pytest.raises(InvalidAssessor):
        make_assessor(clerk_user_id="  ")


def test_role_accepts_the_raw_string_from_the_database():
    assert make_assessor(role="admin").role is Role.ADMIN


def test_unknown_role_is_rejected():
    with pytest.raises(InvalidAssessor, match="unknown role"):
        make_assessor(role="superuser")


def test_assign_role_promotes():
    assessor = make_assessor()
    assessor.assign_role("admin")
    assert assessor.is_admin

    with pytest.raises(InvalidAssessor):
        assessor.assign_role("wizard")


def test_update_profile_reports_whether_anything_changed():
    assessor = make_assessor(email="a@b.com", display_name="Ada")
    assert assessor.update_profile("a@b.com", "Ada") is False
    assert assessor.update_profile("new@b.com", "Ada") is True
    assert assessor.email == "new@b.com"


def test_update_profile_ignores_missing_claims():
    # A Clerk JWT template without email/name must not wipe the stored profile.
    assessor = make_assessor(email="a@b.com", display_name="Ada")
    assert assessor.update_profile(None, None) is False
    assert assessor.email == "a@b.com"


def test_automated_assessor_has_config_identity_and_no_credential():
    assessor = make_automated()
    assert assessor.kind is Kind.AUTOMATED
    assert assessor.clerk_user_id is None


def test_automated_assessor_rejects_a_clerk_credential():
    with pytest.raises(InvalidAssessor, match="no external credential"):
        make_automated(clerk_user_id="user_abc")


@pytest.mark.parametrize("missing", ["name", "version", "instrumentId"])
def test_automated_assessor_requires_its_source_config_identity(missing):
    config = {
        "name": "structural",
        "version": "1",
        "instrumentId": "learnpack-course-qa",
    }
    del config[missing]
    with pytest.raises(InvalidAssessor, match=f"source_config.{missing}"):
        make_automated(source_config=config)


def test_unknown_kind_is_rejected():
    with pytest.raises(InvalidAssessor, match="unknown kind"):
        make_assessor(kind="cyborg")
