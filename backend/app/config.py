"""Settings from environment (frameworks layer — see ARCHITECTURE.md §1)."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["clerk", "local"]

# Hosts that can only be your own machine. `AUTH_MODE=local` is refused against anything else.
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})


def database_host(url: str) -> str:
    """The host of a SQLAlchemy URL, or "" if there is none to read."""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""

    # How a request's identity is established (ADR-0008). `clerk` verifies a JWT against the
    # provider's JWKS; `local` trusts a plain header so the app runs with no accounts at all.
    # Defaulting to `clerk` is deliberate: turning authentication off must be explicit.
    auth_mode: AuthMode = "clerk"
    # When set, the test suite runs against this database instead of `database_url`.
    # Only tests read it (see tests/conftest.py); the app never does.
    test_database_url: str = ""

    # Comma-separated emails created as admin on their FIRST login. Bootstrap only: it never
    # changes an existing assessor's role (see ResolveAssessor._initial_role).
    admin_emails: str = ""

    clerk_issuer: str = ""
    # Derived from the issuer when left empty (see `jwks_url`).
    clerk_jwks_url: str = ""
    clerk_secret_key: str = ""

    # Comma-separated. Kept as a plain string because pydantic-settings would otherwise
    # expect JSON for a list field.
    allowed_origins: str = "http://localhost:3000"

    environment: str = "development"

    @model_validator(mode="after")
    def _local_auth_stays_local(self) -> "Settings":
        """The rules that keep the dev bypass out of any real environment (ADR-0008).

        `get_settings()` runs while importing `app.main`, so a misconfigured deploy fails to
        boot instead of serving an unauthenticated API.

        Two conditions, because each covers the other's blind spot: `ENVIRONMENT` is a label
        nothing enforces (it could simply be unset on the server), while the database host is
        a fact about where the data actually lives.
        """
        if self.auth_mode != "local":
            return self

        if self.environment == "production":
            raise ValueError(
                "AUTH_MODE=local disables authentication and is forbidden with "
                "ENVIRONMENT=production. Use AUTH_MODE=clerk."
            )

        host = database_host(self.database_url)
        if host and host not in LOCAL_DATABASE_HOSTS:
            raise ValueError(
                # ASCII only: this message can surface on a Windows console (cp1252).
                f"AUTH_MODE=local disables authentication, so it only works against a local "
                f"database. DATABASE_URL points at {host!r}: use the local database "
                f"(docker compose up -d) or AUTH_MODE=clerk."
            )
        return self

    @property
    def is_local_auth(self) -> bool:
        return self.auth_mode == "local"

    @property
    def jwks_url(self) -> str:
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        return f"{self.clerk_issuer.rstrip('/')}/.well-known/jwks.json"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def bootstrap_admin_emails(self) -> list[str]:
        return [email.strip() for email in self.admin_emails.split(",") if email.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
