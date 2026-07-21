import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings

# --- where the suite runs -------------------------------------------------------------
# Redirected at import time, before anything can build an engine. With TEST_DATABASE_URL
# pointing at the local Postgres (docker-compose.yml), the suite runs ~500x faster: it is
# latency-bound, and Neon is ~150 ms per round trip from here versus ~0.3 ms locally.
_TEST_URL = get_settings().test_database_url
USING_LOCAL_TEST_DB = bool(_TEST_URL)

if USING_LOCAL_TEST_DB:
    # An env var outranks the .env file in pydantic-settings, so this wins.
    os.environ["DATABASE_URL"] = _TEST_URL
    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    """Bring the local test database up to date once per session.

    Deliberately a no-op against Neon: migrating and seeding automatically is fine for a
    throwaway container, not for the real store.
    """
    if not USING_LOCAL_TEST_DB:
        return

    from alembic import command
    from alembic.config import Config

    from app.cli import DEFAULT_SEED_FILE, run_seed

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(root, "alembic"))
    command.upgrade(config, "head")
    run_seed(DEFAULT_SEED_FILE)


@pytest.fixture(scope="session")
def requires_db() -> None:
    """Skip tests that need a real database when none is configured."""
    if not get_settings().database_url:
        pytest.skip("neither TEST_DATABASE_URL nor DATABASE_URL is set")


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
    """Collect rows created by a test and remove them afterwards.

    Deletion follows the FK order: evaluations/completions → assignments → campaigns →
    contents → assessors. Outbox rows are keyed by the aggregate id that produced them.
    """
    created: dict[str, list] = {"contents": [], "assessors": [], "campaigns": []}
    yield created

    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        for content_id in created["contents"]:
            s.execute(
                text(
                    "DELETE FROM criterion_scores WHERE evaluation_id IN "
                    "(SELECT id FROM evaluations WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM evaluations WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            s.execute(text("DELETE FROM evaluations WHERE content_id = :id"), {"id": content_id})

        for campaign_id in created["campaigns"]:
            s.execute(
                text("DELETE FROM golden_references WHERE campaign_id = :id"), {"id": campaign_id}
            )
            s.execute(
                text("DELETE FROM content_evaluation_completions WHERE campaign_id = :id"),
                {"id": campaign_id},
            )
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM assignments WHERE campaign_id = :id)"
                ),
                {"id": campaign_id},
            )
            s.execute(text("DELETE FROM assignments WHERE campaign_id = :id"), {"id": campaign_id})
            s.execute(
                text("DELETE FROM campaign_contents WHERE campaign_id = :id"), {"id": campaign_id}
            )
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(campaign_id)})
            s.execute(text("DELETE FROM campaigns WHERE id = :id"), {"id": campaign_id})

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

    The identity is resolved **per request**, from a test-only header. A single shared
    override keyed on the client would be wrong: several clients (an admin and two
    evaluators) are alive at the same time in the flow tests.
    """
    from fastapi import HTTPException, Request

    from app.main import app
    from app.platform.security import get_verified_claims

    identities: dict[str, dict] = {}

    def _override(request: Request) -> dict:
        claims = identities.get(request.headers.get("x-test-identity", ""))
        if claims is None:
            raise HTTPException(status_code=401, detail="missing bearer token")
        return claims

    app.dependency_overrides[get_verified_claims] = _override

    def _client(clerk_user_id: str, email: str | None = None, name: str | None = None):
        identities[clerk_user_id] = {"sub": clerk_user_id, "email": email, "name": name}
        return TestClient(app, headers={"X-Test-Identity": clerk_user_id})

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
