"""Settings from environment (frameworks layer — see ARCHITECTURE.md §1)."""

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["clerk", "local"]

# Hosts that can only be your own machine. `AUTH_MODE=local` is refused against anything else.
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})

# The repo's `courses/` tree, which is a local source root without being declared as one
# (ADR-0035 §1). Reserved so nothing can redeclare it under a different path.
BUILTIN_SOURCE_ROOT = "courses"
# A key names a URL prefix and a containment boundary, so it stays boring on purpose.
SOURCE_ROOT_KEY = re.compile(r"^[a-z0-9._-]+$")


def database_host(url: str) -> str:
    """The host of a SQLAlchemy URL, or "" if there is none to read."""
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def parse_source_roots(raw: str) -> list[tuple[str, str]]:
    """The declared `key=path` local source roots, in declared order (ADR-0035 §1).

    Split on the FIRST `=` only, so a Windows path (`runs=D:\\gen\\out`) survives. Raises
    on a declaration nobody could act on; the caller decides what that means, and under
    `AUTH_MODE=local` it means the process does not boot (ADR-0035 §2).
    """
    roots: list[tuple[str, str]] = []
    declared: set[str] = set()
    for entry in (candidate.strip() for candidate in raw.split(",")):
        if not entry:
            continue
        raw_key, separator, raw_path = entry.partition("=")
        key, path = raw_key.strip(), raw_path.strip()
        if not separator or not key or not path:
            raise ValueError(f"local source root '{entry}' is not '<key>=<path>'")
        if not SOURCE_ROOT_KEY.match(key):
            raise ValueError(
                f"local source root key '{key}' must match [a-z0-9._-]+: it names a URL "
                "prefix, not a label"
            )
        if key == BUILTIN_SOURCE_ROOT:
            raise ValueError(
                f"'{BUILTIN_SOURCE_ROOT}' is the built-in local source root (the repo's "
                "courses/ tree); declare the other trees under a different key"
            )
        if key in declared:
            raise ValueError(f"local source root key '{key}' is declared twice")
        declared.add(key)
        roots.append((key, path))
    return roots


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

    # Where the dev static mount serves the repo's `courses/` tree (ADR-0027). Only
    # meaningful under AUTH_MODE=local; the CLI mints local package locators from it.
    local_packages_base_url: str = "http://localhost:8000/packages"

    # Other filesystem trees the dev intake may register from, comma-separated `key=path`
    # (ADR-0035 §1). The repo's `courses/` tree is always available and is not declared here.
    local_source_roots: str = ""
    # Where those trees are served. Deliberately its own setting rather than something
    # derived from `local_packages_base_url`: the built-in root keeps that URL forever
    # because locators registered under it are never rewritten, and deriving a second base
    # from it would break under a path prefix — into a dead locator nobody notices.
    local_sources_base_url: str = "http://localhost:8000/sources"

    # LLM transport (ADR-0034): the environment supplies ACCESS — key and endpoint — never
    # identity. Which model judges is pinned in each assessor's code; pointing the base URL
    # at another OpenAI-compatible endpoint moves the traffic, not the judge.
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    # How long one call may wait before the transport treats it as a transient failure.
    # Access, not identity: a slower or faster deadline changes WHETHER and WHEN an answer
    # arrives, never which one (ADR-0034 §1). Raise it for a long prompt against a slow
    # provider; the default matches the transport's own.
    llm_timeout_seconds: float = 60.0

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

        # The local source roots are validated here and only here (ADR-0035 §2): a malformed
        # declaration is one nobody can act on, and this is the mode that acts on it. A
        # directory that does not exist is NOT checked — that is an environment fact, it
        # warns and is skipped, exactly like the `courses/` tree of a fresh checkout.
        parse_source_roots(self.local_source_roots)
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

    @property
    def declared_source_roots(self) -> list[tuple[str, str]]:
        """The `key=path` roots of `LOCAL_SOURCE_ROOTS`. Validated at construction under
        `AUTH_MODE=local`, which is the only mode that reads this."""
        return parse_source_roots(self.local_source_roots)


@lru_cache
def get_settings() -> Settings:
    return Settings()
