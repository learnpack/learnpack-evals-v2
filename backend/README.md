# backend

FastAPI + Postgres (Neon). Design lives in `../docs/` — **it is the source of truth**.
Hard rules: `../docs/ARCHITECTURE.md`. Names: `../docs/GLOSSARY.md`.
Where development stands today: `../STATUS.md` (this README describes **how it works**, not
what state it is in).

## Setup

```bash
cp .env.example .env      # fill in DATABASE_URL (Neon) and the Clerk keys
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed          # rubric v1 + pedagogical reference data (idempotent)
uv run uvicorn app.main:app --reload
```

`GET /health` verifies that the API boots and the DB responds.

## Local mode: no Clerk and no Neon (ADR-0008)

`AUTH_MODE` decides where a request's identity comes from:

| Mode | Identity | When |
|---|---|---|
| `clerk` (default) | session JWT verified against the JWKS | production and any real environment |
| `local` | the `X-Dev-User: <email>` header, unverified | development, no accounts and no cloud |

Below the claim **it is the same code in both modes**: `ResolveAssessor`, `assessors.role`,
`require_admin`. Local mode does not fork business rules, it only replaces where identity
comes from — the same cut the test suite uses.

```bash
docker compose up -d                       # starts db (5433, tests) and db-dev (5434, development)
cp .env.example .env                       # the example ships in local mode
uv run alembic upgrade head
uv run python -m app.cli seed
uv run python -m app.cli seed-demo         # --reset to start from scratch
```

`seed-demo` leaves 3 users (`admin@local.dev`, `ada.lovelace@local.dev`,
`grace.hopper@local.dev`), the instrument draft imported from `../docs/seed/instruments/`,
the `LearnpackV1` extraction accepted (in the real store that acceptance is the team's
deliberate act, ADR-0012 — the demo auto-accepts because it only runs locally), 2 demo
courses registered with their real frozen packages (auto-profiled by the registration
policy), and an open campaign with **quorum 2** and its 4 assignments, all **pending
evaluation**. Two evaluators is the minimum for inter-rater dispersion and for
`ContentEvaluationCompleted → GoldenReferenceEstablished` to fire.

It goes through the real use cases, so it publishes the same events the UI would. It is
idempotent: running it twice duplicates nothing.

`--reset` **wipes the local dataset** — everything the app writes (courses, profiles,
campaigns, evaluations, acceptances, minted data requirements and `local|` users) — and
reseeds; it does not touch the rubric or the reference data. Deliberately wholesale rather
than "delete what today's demo lists name": editing `DEMO_ASSESSORS`/`DEMO_CONTENTS` is the
normal way to shape a demo, and a scoped delete strands everything the previous version
created. It can only run against a local database, so there is nothing to lose.

What keeps this from leaking into a real environment:

- The code's default is `clerk` (`.env.example` ships `local` because it is the development
  template; in production Render sets the variables). A value that is neither `clerk` nor
  `local` **does not boot**: it is a configuration error, not a silent degrade.
- `AUTH_MODE=local` with `ENVIRONMENT=production` → **the app does not boot**.
- `AUTH_MODE=local` with a `DATABASE_URL` not pointing at localhost → **does not boot
  either**. Two checks because each covers the other's blind spot: `ENVIRONMENT` is a label
  nobody guarantees, while the database host is a fact about where the data lives.
- In `clerk` mode the `X-Dev-User` header **is not read**: it is another adapter, not a
  fallback for a missing token.
- `seed-demo` aborts unless the mode is `local` (it cannot write demo data into Neon by
  mistake).
- `GET /dev/identities` — the list feeding the frontend's user picker — 404s outside local
  mode.

## Clerk (ADR-0004)

Clerk's default session token **carries neither email nor name**. Create a **JWT template**
in the Clerk dashboard with these claims:

```json
{ "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
```

The backend tolerates their absence (the profile stays `NULL`), but without them you cannot
identify the SMEs or use `set-role`.

**Create the template before anyone signs in.** The `email` claim also decides the first
admin's initial role, and that decision is taken **exactly once** — see the order in
[Preparing an environment](#preparing-an-environment--order-matters).

### Roles and the first admin (ADR-0007)

`assessors.role` is the **source of truth** for authorization, and **login never changes
anyone's role** — authenticating cannot escalate privileges.

For bootstrap (an admin is needed before an admin exists to create one) there is
`ADMIN_EMAILS`: a **provisioning** allowlist, not an authorization one. It only decides the
role a **new** assessor is created with:

```bash
ADMIN_EMAILS=you@yourcompany.com,other@yourcompany.com
```

- Email on the list and the person has **never signed in** → created as `admin`.
- Email on the list but the person **already exists** as `evaluator` → **stays** `evaluator`.
- An existing `admin` you **remove** from the list → **stays** `admin`.
- No `email` claim (missing JWT template) → `evaluator`.

This is safe **because access is invite-only**: nobody can register with an admin's email
without the invitation. If you ever disable invite-only, revisit ADR-0007.

To change the role of someone who already exists, the only path is:

```bash
uv run python -m app.cli set-role --email you@yourcompany.com --role admin
```

### Preparing an environment — **order matters**

This sequence runs **once per environment** (one Clerk instance = one environment), before
anyone signs in.

> ⚠️ **The JWT template with the `email` claim must exist BEFORE the admin's first login.**
> Without that claim the assessor is created as `evaluator` (a safe degrade), and since the
> allowlist applies **once, at row creation**, adding the template later does not rescue it.
> Two individually correct behaviors that, in the wrong order, leave the admin born an
> evaluator.

1. **Render:** `ADMIN_EMAILS=<the admin's email>` (and wait for the redeploy to finish).
2. **Clerk:** create the **JWT template** with the `email` claim (above) and invite both
   accounts. **Nobody signs in yet.**
3. **Only now:** the admin signs in. Verify with `GET /me` that it says `"role": "admin"`.
4. The evaluator signs in → stays `evaluator`.
5. Load the courses (`import-learnpack`) and open the campaign from the admin UI.

**If you got the order wrong** (the admin already signed in and landed as `evaluator`):
nothing to delete, no allowlist to touch — fix it with

```bash
uv run python -m app.cli set-role --email <admin email> --role admin
```

which is the only mechanism to change the role of someone who already exists.

## Layers (Dependency Rule)

| Folder | Layer | May import |
|---|---|---|
| `app/modules/*/domain` | Domain | no framework — **pure Python** |
| `app/modules/*/application` | Application | its own domain + `shared`; **defines the ports** |
| `app/modules/*/infrastructure` | Adapters | application + domain (repos, routers, ACLs, extraction adapters) |
| `app/platform`, `app/main.py` | Frameworks | everything; injects the dependencies |

## A module's public surface (ARCHITECTURE.md §3)

Each module exposes its contract in `modules/<m>/public.py`: query DTOs, its event names,
and a `get_<m>_queries` provider for `Depends` injection that **builds its own repo
inside**. Other modules import **only** from there — never from
`modules/<other>/infrastructure` (that would couple them to the concrete adapter instead of
the port) nor from `modules/<other>/domain`.

Sole exception: the composition root (`main.py`, `cli.py`, `platform/`), whose job *is* to
inject concrete adapters.

`tests/test_architecture.py` makes the rule executable: the build fails if someone breaks
it. It runs on every `pytest`, without a DB.

## Events-first (ADR-0003)

Publishing an event = an `INSERT` into `events` with the use case's session, in the same
transaction as the aggregate (`OutboxEventPublisher`). After commit, the in-process
`EventDispatcher` delivers the event to subscribed policies. Handlers must be idempotent by
`event_type + aggregate_id`, so reprocessing from the `events` table is safe.

Policies wired today (`main.py`): the completion chain of the human path (below) and, from
slice 2, `ContentVersionRegistered → ProfileContent` — registering content auto-profiles it
**iff** the format's extraction is accepted.

## Commands

```bash
docker compose up -d     # local Postgres: db (tests) + db-dev (development)
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy              # types (strict, scope in pyproject.toml)
```

All of it also runs in CI on every PR and push to main (`.github/workflows/ci.yml`): lint +
format + types + backend suite (with Postgres as a service container) + frontend typecheck
(`npm run typecheck`).

### Why tests run against local Postgres

The suite is **latency-bound**, not CPU-bound: each query to Neon (`us-east-1`) costs
~150 ms from Latam, and an integration test makes over a hundred. That is ~20 s per test
and a +10 min suite. Against local Postgres the same query costs ~0.3 ms.

With `TEST_DATABASE_URL` set (see `.env.example`), `tests/conftest.py` redirects the suite
to that DB and **migrates and seeds it by itself**. Without it, tests run against
`DATABASE_URL` — valid, just slow; in that case conftest does **not** migrate or seed
anything (the real store is never touched automatically).

Neon remains the store of truth: migrations, deploy and the final smoke check.

## Unit of work

`app/platform/uow.py` is each use case's transactional boundary: it holds the `Session`,
the `OutboxEventPublisher` over that same session, and the dispatcher. `uow.commit()`
commits and **then** dispatches the now-durable events. Use cases receive `uow` + the ports
they need; concrete adapters are injected from the router.

## Completion policy (ADR-0002)

On `EvaluationSubmitted`, `orchestration` marks `submitted` every open assignment of
`(assessor, content)` whose campaign uses the same `instrumentVersion` — so one evaluation
can satisfy several campaigns — and publishes `ContentEvaluationCompleted` when
`COUNT(assignments submitted) ≥ required`.

It runs **after** the evaluation's commit, in its own transaction: completion is
**eventual**, not a transactional invariant. It is idempotent (`ON CONFLICT DO NOTHING` +
publish only on insert), so reprocessing from `events` is safe.

## Golden dataset and reports

The complete human chain, all through events (`../docs/design/08-code.md` §5):

```
EvaluationSubmitted → (orchestration) ContentEvaluationCompleted
                    → (golden)        GoldenReferenceEstablished
```

Golden keeps no count of its own: it asks orchestration for coverage through its query port
and applies its rule (`coverage ≥ threshold`). Idempotent like the quorum policy.

**Reporting** (ADR-0006) composes the other modules through their `public.py` and
aggregates in Python — no cross-module JOINs and no read-model tables. Endpoints:
`GET /admin/reports/scores` (each course's per-criterion profile: per-criterion average
across assessors + inter-rater dispersion; **no aggregate score across criteria**,
ADR-0011) and `GET /admin/progress` (who evaluated what, cross-campaign).

Two aggregation rules not to confuse:
- A **repetition** is the same assessor on the same `(content, instrumentVersion)` — it
  collapses to the most recent, because it is a correction. Evaluating **two different
  courses** is not a repetition.
- Dispersion with a single rater is `null`, not `0`: there is no agreement to measure.

## Instruments and content profiling (slice 2)

- **Instrument authoring is file-based** (`../docs/seed/instruments/*.yaml`, one file per
  version, named `{instrument_id}-{version}.yaml`); there is no authoring UI. Publishing
  is always a human act, and a published version never changes — any change is a new
  version. When to use which command:

  | You want to… | Then… |
  |---|---|
  | Create an instrument, or keep editing one that is still a **draft** | Edit the YAML and `uv run python -m app.cli import-instrument --file <yaml>` — the draft is replaced in place, as often as needed (no bump involved). Import also mints the `data_requirement` ids the extraction conforms to (ADR-0014). |
  | Lock a draft so evaluations and studies can rely on it | `uv run python -m app.cli publish-instrument --id <version-id> --email <admin>`, or the Publish button in `/admin/instruments`. Publish validates the full evidential argument; from here the version is immutable. |
  | Change anything in a **published** version — a threshold, a wording, a new criterion | `uv run python -m app.cli bump-instrument --file <yaml> [--to vN] [--reason "..."]` clones the YAML into the next version's file **textually** (header comments and block-scalar style survive; only `version:` and, with `--reason`, `revision_reason:` change), then: edit the new file → `import-instrument` → `publish-instrument`. Claim/criterion ids stay stable across versions — the lineage. |
  | Change the declaration of an **existing** `data_requirement` — reword the definition (same meaning) or adjust its `value_domain` | Edit it in the YAML and add `--revise-definitions` to `import-instrument`: the deliberate act that lifts the ADR-0014/0020 lint; each revision is applied and reported old → new. Without the flag the lint blocks — the guardrail against silently rewriting the contract adapters conform to. |
  | Express a **different** concept than an existing `data_requirement` | Do NOT revise it — mint a new id with its own definition (ADR-0014: same meaning → alias or revision; similar-but-different → new id). |

  Versions are cheap by design: iterate by bumping and deprecate freely — what
  reproducibility hangs on is the version a study **pins**, never how many versions came
  before it. `bump-instrument` refuses collisions (target file on disk, target version in
  the db) and self-checks the textual edit before writing, so it never produces a corrupt
  or overwritten file.
- **Extraction** (`content_profiling`): the `LearnpackV1` adapter derives a cited profile
  from the package's artifacts — no inference, absence is a result (ADR-0009). Automatic
  profiling on registration is armed by the human acceptance of the adapter version:
  `uv run python -m app.cli accept-extraction --package-format LearnpackV1 --email <admin>`
  (ADR-0012), after reviewing samples in `/admin/profiles` or via
  `uv run python -m app.cli profile-content --content-id <id>`.
- **Automated evaluation** (`evaluation`): calibrate an instrument — drafts included —
  against real content with
  `uv run python -m app.cli evaluate --content-id <id> --instrument-version-id <id> --dry-run`
  (prints the five-state outcome table and the claim summary; persists nothing). The real
  path requires a **published** version and a **ratified** assessor (ADR-0019):
  `uv run python -m app.cli ratify-assessor --name structural --version 1
  --instrument-version-id <id> --email <admin>` — the initial registration is the first
  ratification; against a later version of the same lineage the diff is computed
  mechanically and only changed/new **executed** criteria demand
  `--confirm <criterion-id>`. Then `evaluate` without `--dry-run` persists the evaluation
  (outcomes + raw metrics) and the judgment policy derives claims, coverage and findings.

## Registering courses

The canonical intake is **discovery** (ADR-0027): declare a package source and the system
reads the artifact list, the descriptor and a content hash from the package itself.

```bash
# one course, by URL or by a local directory under the repo's courses/ tree
uv run python -m app.cli register-package --source https://my-course.learn-pack.com --generator <uuid|unknown>
uv run python -m app.cli register-package --source ../courses/unknown/my-course --generator unknown

# every course under courses/<name>@<version>/ and courses/unknown/ (batch)
uv run python -m app.cli register-package --all
```

Local sources need the dev API running (`AUTH_MODE=local`): it serves the repo's
gitignored `courses/` tree at `/packages` (base URL: `LOCAL_PACKAGES_BASE_URL`, default
`http://localhost:8000/packages`), so registered locators and `consumable_url` are honest
http URLs — brief intake and profiling then work exactly as with remote packages.
Re-importing an unchanged course is a no-op (content hash); the same declared version with
changed content is refused. See `../courses/README.md` for the folder convention.

`import-learnpack --file courses.json` remains for hand-composed batches that already
carry their artifact lists (canonical JSON shape only).

## Modules

identity · evaluand_registry · evaluation_design · content_profiling · evaluation ·
orchestration · golden_dataset · reporting. Each with `domain/`, `application/` and
`infrastructure/`, and its contract in `public.py`.

The plans that originated them are frozen in `../docs/design/08-code.md` (slice 1) and
`../docs/design/13-code-qa.md` (slice 2); progress lives in `../STATUS.md`.
