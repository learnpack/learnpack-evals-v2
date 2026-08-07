# ADR-0008 — Local mode: running the system without Clerk or Neon

**Status:** accepted · **Date:** 2026-07 · **Context:** Identity & Access (generic) + tooling

## Context
Some collaborators work **exclusively on rubrics, metrics and evaluations**: they edit
`docs/seed/rubric-v1.json`, evaluate courses and look at the reports. They do not touch infrastructure.

To bring up the repo today they need (a) a Clerk account with a JWT template and an invitation
(ADR-0004) and (b) a database on Neon (ADR-0003). That is a disproportionate barrier for that work,
and it also couples iteration on the rubric to two external services.

The constraint to respect: the role lives in `assessors.role` and **logging in never changes a role**
(ADR-0007). No development shortcut may erode that, nor become a way to
get into a real environment.

The cut already existed: `tests/conftest.py::as_user` runs the entire suite —including the full
authorization chain— overriding **only** `get_verified_claims`. Clerk was already isolated
behind "give me a dict of claims".

## Decision
**`AUTH_MODE` with two adapters behind the same dependency.** `clerk` (default) verifies the JWT
against the JWKS; `local` builds the same claims from the `X-Dev-User: <email>` header.

Everything below the claim —`ResolveAssessor`, assessor creation, `assessors.role`,
`require_admin`— is **the same code in both modes**. Local mode does not fork business
rules: it only replaces where the identity comes from.

Hard rules that keep this from leaking:

| Rule | Where |
|---|---|
| The code default is `clerk`; a value other than `clerk`/`local` **does not start** (on the front, which cannot fail like that, it falls back to `clerk`) | `Settings.auth_mode`, `lib/auth/mode.ts` |
| `AUTH_MODE=local` + `ENVIRONMENT=production` → **the app does not start** | `Settings` validator |
| `AUTH_MODE=local` + remote `DATABASE_URL` → **the app does not start** | `Settings` validator |
| In `clerk` mode the `X-Dev-User` header **is not read** (it is not a fallback for a missing token) | `get_verified_claims` |
| `seed-demo` and `GET /dev/identities` only exist in local mode | `app/cli.py`, `platform/dev_router.py` |

The guard has **two** conditions and not one: `ENVIRONMENT` is a label that nothing forces you to
set —a service created without that variable has it at `development`—, while the host of
`DATABASE_URL` is a fact about where the data lives. To serve an API without authentication
you would need, besides requesting the mode explicitly, to be pointing at a local database.

Complements that make the mode genuinely usable:
- **Its own local database** (`db-dev`, port 5434) separate from the tests one, because the suite's
  `cleanup` fixture deletes rows.
- **`app.cli seed-demo`**: 3 users (1 admin + 2 evaluators), 2 courses, 1 open campaign with
  quorum 2 and the 4 assignments — **all pending**, no preloaded evaluations. Idempotent,
  with `--reset`. It goes through the real use cases, so it publishes the real events. Being a
  seeder and not a login, it **aligns the role** of a demo user that already exists: whoever logged in
  before seeding was born `evaluator` and would be left with 403 across the entire admin console. The
  ADR-0007 invariant that is not touched is that *logging in* never changes a role.
- **`--reset` empties the entire local dataset** (courses, campaigns, evaluations and `local|`
  users), not "whatever the code's lists say today". Editing those lists is the normal way
  of putting together a demo, and a scoped deletion orphans what the previous version created —a
  renamed user still showing up in the selector, a replaced course with no campaign— with
  no way to clean it up. It is safe precisely because of the guard: it only runs against a local
  database.
- **User selector** on `/sign-in`, fed by `GET /dev/identities` (the DB is the source
  of truth, not a hardcoded list in the front). Switching users reloads the page to
  discard the previous one's query cache.

Two evaluators is not a whim: with only one, inter-rater is `null` and the
`ContentEvaluationCompleted → GoldenReferenceEstablished` chain never fires. The minimal dataset to exercise
the metrics needs quorum 2.

## Consequences
- (+) `docker compose up -d` + two commands and the whole app runs, without accounts or cloud.
- (+) The production path does not change: same default, same tests, same deploy.
- (+) The loop for whoever works on the rubric becomes: edit the JSON → `app.cli seed` → refresh.
- (−) Two authentication paths; the local one is only exercised in `tests/test_auth_local.py`. Mitigated
  by keeping the cut finite: local mode **only** fabricates claims. If it ever
  needed role logic of its own, that would be the signal that the cut moved to the wrong place.
- (−) `X-Dev-User` remains in CORS `allow_headers` in production too. It is inert (in `clerk`
  mode nobody reads it) and avoids maintaining two CORS configurations.
- (−) The front bundles both adapters. Irrelevant in size, and it makes the switch an env
  var, not a different build.

## Alternatives considered
- **Local JWT signed with HS256** (an endpoint that issues dev tokens) → rejected: more faithful to the
  real path, but adds token issuance and key handling for an audience that should not
  need to know a token exists. The cut would end up in the same place anyway.
- **Shared Clerk instance for development** → rejected: still requires an account,
  an invitation and network; it does not solve the problem, it centralizes it.
- **Auto-detecting local mode when the Clerk keys are missing** → rejected: a badly loaded variable
  in a deploy would turn the app into a system without authentication. Activation has
  to be explicit and, in addition, incompatible with `ENVIRONMENT=production`.
- **A single fictitious user, no selector** → rejected: without an admin + two evaluators you cannot
  exercise the quorum, the golden, or the inter-rater dispersion.
- **SQLite instead of local Postgres** → rejected: the schema uses JSONB and partial unique indexes
  (08-code.md §3); a different engine in development would produce real divergences.

## Implementation
`AUTH_MODE` → `Settings.auth_mode` / `is_local_auth`; `platform/auth_local.py` (claims from the
header) chosen in `platform/security.py::get_verified_claims`; `platform/dev_router.py`;
`app/cli.py seed-demo`; `docker-compose.yml` (`db-dev`). Frontend: `src/lib/auth/`
(`mode.ts` + adapters `clerk.tsx` / `local.tsx`), consumed by `layout.tsx`, `app-header.tsx`,
`sign-in`, `lib/api/hooks.ts` and `middleware.ts`.
Tests: `backend/tests/test_auth_local.py` (6 cases, including the header ignored in `clerk` mode and
startup forbidden in production).
