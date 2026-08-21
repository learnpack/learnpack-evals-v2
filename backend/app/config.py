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
    # The connection pool, declared rather than inherited. These are SQLAlchemy's own
    # defaults, so nothing moves by naming them — what changes is that the number becomes
    # movable, because it bounds something real: `batch_max_courses` below is limited by this
    # pool and by nothing else, and a lever nobody can reach is not a lever.
    #
    # What consumes it: a batch worker holds TWO concurrent sessions, its own and the one the
    # policy opens when the evaluation commits (a policy runs in its own transaction,
    # ADR-0003). So `pool_size + max_overflow` has to cover `2 x workers` with room left for
    # whatever else the process is doing. Raising it past what the SERVER allows only moves
    # the error: the local Postgres serves 100 connections, and a managed one has its own.
    db_pool_size: int = 5
    db_max_overflow: int = 10

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
    # Where Clerk's invitation link lands. Derived from the first allowed origin when empty,
    # the way `clerk_jwks_url` is derived from the issuer — one env var fewer to forget, and
    # the frontend origin is already declared for CORS.
    clerk_invitation_redirect_url: str = ""

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
    # identity. Which model judges is pinned in each assessor's code, so moving the base URL
    # moves the traffic, not the judge. It has to keep speaking OpenRouter's API all the
    # same: the assessors pin OpenRouter model ids and send its `provider` routing
    # (ADR-0038), and `provider` is declared in their SOURCE_CONFIG — so another provider is
    # a new assessor version, not a new endpoint.
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    # Where each run's LLM attempts are written, one JSON object per attempt: the prompts
    # as sent and the raw answers, which is the only way to tell a bad prompt from a bad
    # model afterwards. Empty means no trace file — the setting is how a machine opts in,
    # so a deployment that should not be writing prompts to disk simply never sets it.
    llm_trace_dir: str = ""
    # How long one call may wait before the transport treats it as a transient failure.
    # Access, not identity: a slower or faster deadline changes WHETHER and WHEN an answer
    # arrives, never which one (ADR-0034 §1). Raise it for a long prompt against a slow
    # provider; the default matches the transport's own.
    llm_timeout_seconds: float = 60.0
    # How many requests may be IN FLIGHT at once, across everything this process runs. A
    # ceiling on concurrency, not a rate: the transport already survives a rate limit by
    # backing off on 429 with `Retry-After`, and what no reactive half can undo is asking
    # for far more than the account allows in the first place. Access, not identity, on the
    # same reasoning as the timeout: it changes when an answer arrives, never which one.
    # It lives at the transport because that is the only place that sees every call however
    # many levels of fan-out sit above it — a batch over courses, and inside each one an
    # assessor task that asks several questions at once, whose product no per-level cap
    # could bound.
    #
    # The number comes from OUR demand, because the endpoint declares none: OpenRouter
    # publishes rate limits (requests per minute and per day) only for the `:free` model
    # variants, states no concurrency cap for paid ones, and governs capacity per account —
    # so more keys buy nothing and there is no figure to read off the API.
    #
    # Our demand is one evaluation's widest moment, and ADR-0048 widened it: the derivation
    # now looks at every judgeable criterion together, so a course's peak is its concept map
    # (one call plus one per module, seven on the drafts measured) alongside the criteria a
    # model judges (five, one vote at a time) and the single-call tasks (four) — sixteen.
    #
    # A ceiling below that does not save anything; it moves the wait into this queue, where
    # it is recorded as latency and reads like a slow model. That is measured, not feared:
    # at a ceiling of seven all seven map calls generated at 106-134 tokens per second with
    # no 429 and no retry, where at four the three that waited for a slot recorded 46-71.
    #
    # What is NOT measured is whether the account is served sixteen at once, because only a
    # real run can say. The transport backs off on 429 honouring `Retry-After`, so being
    # wrong here costs retries rather than correctness.
    #
    # A BATCH multiplies it again by the courses in flight. How many those are is
    # `batch_max_courses`, a different question with a different limit.
    llm_max_concurrency: int = 16
    # How many COURSES a batch evaluates at a time (`evaluate-study`, the console's batch).
    # Separate from the ceiling above since the concept map's fan-out made them independent:
    # one course now asks for several calls at once, so "courses in flight" and "requests in
    # flight" stopped being the same number and one cannot serve as the other's default.
    #
    # What bounds this one is the DATABASE, not the endpoint. Each worker holds two concurrent
    # sessions (see `db_pool_size`), so the workers a pool serves is `(size + overflow) / 2`
    # minus whatever else the process needs — seven against today's fifteen, with one
    # connection left over. Six is deliberately not that edge: a pool that runs out does not
    # slow a batch down, it makes a checkout wait `pool_timeout` and then raise, and a failure
    # nobody named ends the whole batch rather than one course.
    #
    # Six rather than four because it was measured, over one study of six courses: four at a
    # time took 304 s against 963 s of course time, six-plus took 180 s against 954 s — 3.2x
    # against 5.3x — with no retry, no 429, and the map's calls generating at the same 97-141
    # tokens per second either way. The requests ceiling is not what is holding a batch back.
    # `backend/README.md` has the arithmetic for going higher, which means raising the pool in
    # the same breath.
    batch_max_courses: int = 6
    # How many ARTIFACT fetches may be in flight at once — the same kind of ceiling as
    # `llm_max_concurrency`, at the other transport. A package's declared surface is read a
    # file at a time (73 of them on the course measured), and those reads are independent, so
    # they go out together; this is what keeps "together" from meaning "all seventy-three".
    #
    # It is deliberately more conservative than the LLM's, for a reason that has nothing to do
    # with how much either endpoint can take. There the account is ours and the transport backs
    # off on 429 honouring `Retry-After`, so overshooting costs retries. Here the origin is
    # somebody else's course server, this transport has no backoff at all, and a fetch that
    # fails refuses the whole registration (ADR-0027) — so overshooting costs a package that
    # reads as broken when what happened is that we asked too fast.
    #
    # Eight, measured against one real origin — a 39-artifact course on `learn-pack.com`, where
    # a request costs about half a second. Reading its declared surface took 19.6 s one file at
    # a time, 6.4 s at four, 4.4 s at eight, 3.2 s at sixteen and 3.1 s at twenty-four, with no
    # failure at any of them. So the curve is flat past sixteen — what is left by then is the
    # part that cannot fan out at all: three manifests read one after the next, because each one
    # names the next.
    #
    # It stops at eight rather than sixteen because that measurement is ONE origin, and this
    # setting applies to every origin a course may be served from. The LLM ceiling could be
    # raised on its own measurement since there is one endpoint behind it and being wrong there
    # costs retries; being wrong here costs a registration. Sixteen buys about a second on the
    # origin measured, which is the trade to weigh if it ever matters.
    http_max_concurrency: int = 8

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
    def invitation_redirect_url(self) -> str:
        """The page Clerk sends an invited person to. Our own sign-in, not Clerk's hosted
        one: the app is the thing they were invited to."""
        if self.clerk_invitation_redirect_url:
            return self.clerk_invitation_redirect_url
        origins = self.cors_origins
        return f"{origins[0].rstrip('/')}/sign-in" if origins else ""

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
