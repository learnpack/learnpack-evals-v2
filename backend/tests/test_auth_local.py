"""Local development mode: identity from a header, and the guards around it (ADR-0008).

The point of these tests is not the happy path — it is that the bypass cannot leak: the dev
header does nothing under `AUTH_MODE=clerk`, and the mode itself cannot coexist with
`ENVIRONMENT=production`.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import LOCAL_DATABASE_HOSTS, Settings, database_host, get_settings
from app.platform.auth_local import DEV_USER_HEADER, display_name_for

LOCAL_DB = "postgresql+psycopg://postgres:postgres@localhost:5434/learnpack_evals_dev"
REMOTE_DB = "postgresql+psycopg://user:pw@ep-x.us-east-1.aws.neon.tech/db?sslmode=require"


def is_local_database(url: str) -> bool:
    host = database_host(url)
    return not host or host in LOCAL_DATABASE_HOSTS


@pytest.fixture
def local_auth(monkeypatch):
    """Run the app in local auth mode. The setting is read per request, not at import."""
    if not is_local_database(get_settings().database_url):
        pytest.skip("AUTH_MODE=local only builds against a local database (TEST_DATABASE_URL)")
    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def clerk_auth(monkeypatch):
    """Force the default mode.

    Not redundant with the default: a contributor running the app locally has
    `AUTH_MODE=local` in their `.env` (backend/README.md), and `Settings` reads it.
    """
    monkeypatch.setenv("AUTH_MODE", "clerk")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(requires_db):
    from app.main import app

    return TestClient(app)


def test_header_identity_creates_and_resolves_the_assessor(client, local_auth, cleanup, unique):
    """The whole chain below the claims is the real one: assessor created, role evaluator."""
    email = f"dev.user.{unique}@local.test"

    response = client.get("/me", headers={DEV_USER_HEADER: email})

    assert response.status_code == 200, response.text
    body = response.json()
    cleanup["assessors"].append(body["assessor_id"])
    assert body["role"] == "evaluator"
    assert body["email"] == email
    assert body["display_name"].startswith("Dev User")


def test_display_name_is_derived_from_the_email():
    assert display_name_for("ada.lovelace@local.dev") == "Ada Lovelace"
    assert display_name_for("grace-hopper@local.dev") == "Grace Hopper"
    assert display_name_for("admin@local.dev") == "Admin"


def test_local_mode_without_the_header_is_unauthorised(client, local_auth):
    assert client.get("/me").status_code == 401


def test_the_dev_header_does_nothing_in_clerk_mode(client, clerk_auth):
    """No fallback: in the default mode the header is not even read."""
    response = client.get("/me", headers={DEV_USER_HEADER: "admin@local.dev"})

    assert response.status_code == 401


def test_dev_identities_endpoint_only_exists_in_local_mode(client, local_auth, monkeypatch):
    assert client.get("/dev/identities").status_code == 200

    monkeypatch.setenv("AUTH_MODE", "clerk")
    get_settings.cache_clear()
    assert client.get("/dev/identities").status_code == 404


def test_local_auth_is_refused_in_production():
    """A misconfigured deploy fails to boot instead of serving an unauthenticated API."""
    with pytest.raises(ValidationError, match="forbidden with ENVIRONMENT=production"):
        Settings(auth_mode="local", environment="production", database_url=LOCAL_DB)

    # The safe combinations still build.
    Settings(auth_mode="local", environment="development", database_url=LOCAL_DB)
    Settings(auth_mode="clerk", environment="production", database_url=REMOTE_DB)


def test_local_auth_is_refused_against_a_remote_database():
    """`ENVIRONMENT` is a label nothing enforces; where the data lives is a fact."""
    with pytest.raises(ValidationError, match="local database"):
        Settings(auth_mode="local", database_url=REMOTE_DB)

    Settings(auth_mode="local", database_url=LOCAL_DB)
    Settings(auth_mode="clerk", database_url=REMOTE_DB)
