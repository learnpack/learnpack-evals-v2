"""Identity end to end: Clerk claims → Assessor → authorisation (ADR-0004)."""

from sqlalchemy import text


def test_first_login_creates_an_evaluator(as_user, cleanup, session, unique):
    client = as_user(f"user_{unique}", f"{unique}@example.com", "Ada Lovelace")
    response = client.get("/me")

    assert response.status_code == 200
    body = response.json()
    cleanup["assessors"].append(body["assessor_id"])

    # New assessors are evaluators; only the CLI grants admin.
    assert body["role"] == "evaluator"
    assert body["email"] == f"{unique}@example.com"
    assert body["display_name"] == "Ada Lovelace"


def test_repeated_login_is_idempotent(as_user, cleanup, session, unique):
    clerk_id = f"user_{unique}"
    client = as_user(clerk_id, f"{unique}@example.com", "Ada")

    first = client.get("/me").json()
    second = client.get("/me").json()
    cleanup["assessors"].append(first["assessor_id"])

    assert first["assessor_id"] == second["assessor_id"]
    count = session.execute(
        text("SELECT count(*) FROM assessors WHERE clerk_user_id = :c"), {"c": clerk_id}
    ).scalar_one()
    assert count == 1


def test_login_refreshes_a_changed_profile(as_user, cleanup, unique):
    clerk_id = f"user_{unique}"
    first = as_user(clerk_id, f"{unique}@example.com", "Ada").get("/me").json()
    cleanup["assessors"].append(first["assessor_id"])

    updated = as_user(clerk_id, f"{unique}@example.com", "Ada Lovelace").get("/me").json()
    assert updated["display_name"] == "Ada Lovelace"


def test_login_never_changes_the_role(as_user, cleanup, promote, session, unique):
    """Authentication must not be able to escalate privileges."""
    clerk_id = f"user_{unique}"
    email = f"{unique}@example.com"
    body = as_user(clerk_id, email, "Ada").get("/me").json()
    cleanup["assessors"].append(body["assessor_id"])

    promote(email)
    assert as_user(clerk_id, email, "Ada").get("/me").json()["role"] == "admin"

    # A later login with a fresh profile still leaves the role alone.
    assert as_user(clerk_id, email, "Ada L.").get("/me").json()["role"] == "admin"


def test_missing_token_is_unauthorised(requires_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/me").status_code == 401


def test_evaluator_cannot_reach_admin_endpoints(as_user, cleanup, unique):
    client = as_user(f"user_{unique}", f"{unique}@example.com", "Ada")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get("/admin/contents").status_code == 403


def test_admin_can_reach_admin_endpoints(as_user, cleanup, promote, unique):
    email = f"{unique}@example.com"
    client = as_user(f"user_{unique}", email, "Ada")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    promote(email)
    assert client.get("/admin/contents").status_code == 200


def test_automated_assessor_round_trips_through_the_repository(cleanup, session, unique):
    from app.modules.identity.domain.assessor import Assessor, Kind
    from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
    from app.shared.domain.ids import new_id

    repository = SqlAlchemyAssessorRepository(session)
    name = f"structural-{unique}"
    assessor = Assessor(
        id=new_id(),
        clerk_user_id=None,
        display_name=f"{name} v1",
        kind=Kind.AUTOMATED,
        source_config={
            "name": name,
            "version": "1",
            "instrumentId": "learnpack-course-qa",
            "coverage": {"executes": ["cr-a"], "abstains": {"cr-b": "semantic judgment"}},
        },
    )
    repository.add(assessor)
    session.commit()
    cleanup["assessors"].append(str(assessor.id))

    found = repository.get_automated(name, "1")
    assert found is not None
    assert found.id == assessor.id
    assert found.kind is Kind.AUTOMATED
    assert found.clerk_user_id is None
    assert found.source_config["coverage"]["executes"] == ["cr-a"]
    assert repository.get_automated(name, "2") is None
