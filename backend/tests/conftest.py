import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings


@pytest.fixture(scope="session")
def requires_db() -> None:
    """Skip tests that need a real database when DATABASE_URL is not configured."""
    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set")


@pytest.fixture
def session(requires_db):
    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        yield s


@pytest.fixture
def unique() -> str:
    """A per-test suffix, so runs against the shared Neon never collide."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def cleanup(requires_db) -> Iterator[dict[str, list]]:
    """Collect rows created by a test and remove them afterwards."""
    created: dict[str, list] = {"contents": [], "assessors": []}
    yield created

    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        for content_id in created["contents"]:
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(content_id)})
            s.execute(text("DELETE FROM contents WHERE id = :id"), {"id": content_id})
        for assessor_id in created["assessors"]:
            s.execute(text("DELETE FROM assessors WHERE id = :id"), {"id": assessor_id})
        s.commit()


@pytest.fixture
def as_user(requires_db, cleanup):
    """A TestClient authenticated as a given Clerk identity.

    Only `get_verified_claims` is overridden — the signature check is covered by
    tests/test_clerk_jwt.py. Everything downstream (ResolveAssessor, require_admin) is the
    real thing, which is the point: this exercises the authorisation chain.
    """
    from app.main import app
    from app.platform.security import get_verified_claims

    def _client(clerk_user_id: str, email: str | None = None, name: str | None = None):
        claims = {"sub": clerk_user_id, "email": email, "name": name}
        app.dependency_overrides[get_verified_claims] = lambda: claims
        return TestClient(app)

    yield _client
    app.dependency_overrides.clear()


@pytest.fixture
def promote(session):
    """Give an assessor the admin role, the way the CLI does."""

    def _promote(email: str) -> None:
        session.execute(
            text("UPDATE assessors SET role = 'admin' WHERE lower(email) = lower(:e)"),
            {"e": email},
        )
        session.commit()

    return _promote


@pytest.fixture
def register_assessor(session, cleanup, as_user):
    """Sign a user in once (creating the Assessor) and return their id."""

    def _register(clerk_user_id: str, email: str, name: str = "Test User"):
        client = as_user(clerk_user_id, email, name)
        response = client.get("/me")
        assert response.status_code == 200, response.text
        assessor_id = response.json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return assessor_id

    return _register
