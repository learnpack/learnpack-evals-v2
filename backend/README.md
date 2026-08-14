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

**The schema is checked at both doors.** The API and the CLI compare the database's revision
against this checkout's head before doing anything. On a dev box (`AUTH_MODE=local`) a
mismatch **refuses to start** and names the fix; anywhere else it logs a warning and carries
on, because a deploy may start a process while the migration step is still running. A
database it cannot reach says nothing — that is a different failure, with its own reporting.

The reason it exists: a batch once died mid-course on a missing column because the
development database was one migration behind. The test database never is (the suite
migrates it at session start), so a green suite says nothing about the store you run
against — and the cost of finding out late is a half-spent evaluation. If it refuses:
`uv run alembic upgrade head`. If it says the database is at a revision this checkout does
not know, the stale thing is the code: pull.

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
docker compose up -d                       # starts db (15433, tests) and db-dev (15434, development)
cp .env.example .env                       # the example ships in local mode
uv run alembic upgrade head
uv run python -m app.cli seed
uv run python -m app.cli seed-demo         # --reset to start from scratch
```

`seed-demo` leaves 3 users (`admin@local.dev`, `ada.lovelace@local.dev`,
`grace.hopper@local.dev`), the instrument draft imported from `../docs/seed/instruments/`,
the `LearnpackV1` extraction accepted (in the real store that acceptance is the team's
deliberate act, ADR-0012 — the demo auto-accepts because it only runs locally), 2 demo
courses registered with their real frozen packages and profiled by the seeder's own
explicit step (their locators are relative to the frozen fixture tree, and the automatic
policy only reaches http(s) ones — ADR-0029), and an open campaign with **quorum 2** and
its 4 assignments, all **pending
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

Policies wired today (one list in `app/platform/policies.py`, called by both the API and the
CLI so the two processes cannot drift — ADR-0029 §1): the completion chain of the human path
(below) and, from slice 2, `ContentVersionRegistered → ProfileContent` — registering content
auto-profiles it **iff** the format's extraction is accepted **and** every artifact locator
is an http(s) URL. Packages rooted on a filesystem (the seeder's fixtures,
`import-learnpack --base-dir`) are declined in silence and stay on the manual path, which
picks its own fetcher.

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
  `uv run python -m app.cli evaluate --content-id <id> --instrument-version-id <id>
  --assessor <name>:<version> --dry-run`
  (prints the five-state outcome table and the claim summary; persists nothing).
  `--assessor` is always explicit: the registry holds `structural:1` for
  `learnpack-course-qa` and, for `course-drafts-qa`, both `drafts-structural:1` (pure
  code) and `drafts-hybrid:2` (its superset, with LLM-carried criteria) — an instrument
  admits 0..N assessors (ADR-0016), and naming which one is doing the judging is part of
  the act. Mind that judgments do not combine across assessors: the report and the
  fitness read the most recent judgment per content, so within one study evaluate each
  content with ONE assessor, not several. The real
  path requires a **published** version and a **ratified** assessor (ADR-0019):
  `uv run python -m app.cli ratify-assessor --name structural --version 1
  --instrument-version-id <id> --email <admin>` — the initial registration is the first
  ratification; against a later version of the same lineage the diff is computed
  mechanically and only changed/new **executed** criteria demand
  `--confirm <criterion-id>`. The same act is available in the console, on
  `/admin/assessors` (ADR-0036): the Ratify button, and a second step listing each changed
  criterion with the `pass_condition` being confirmed where the CLI takes
  `--confirm`. Both gates run one use case, so they cannot answer differently. Then
  `evaluate` without `--dry-run` persists the evaluation
  (outcomes + raw metrics) and the judgment policy derives claims, coverage and findings.
- **The assessors page** (`/admin/assessors`) is where that state is read: assessors
  grouped by kind (automated by default, humans optional, both), and per automated package
  its coverage plus every version of its lineage with whether it may judge with it, who
  ratified it and when. The automated rows come from `GET /admin/assessor-packages` — the
  in-code registry, now carrying that state — rather than from the `assessors` table, on
  purpose: a package nobody has ratified has no row there at all, and it is the one worth
  acting on. The act itself is `POST /admin/assessor-packages/{name}/{version}/ratify`
  (409 with the criteria to decide, 422 with its cause named for everything else); it is
  composed in `app/platform/ratification_router.py` because it spans Identity and
  Evaluation.
- **LLM-carrying assessors** (ADR-0034): `drafts-hybrid` extracts/classifies with an LLM
  and decides pass/fail in code. It needs `LLM_API_KEY` in the environment (see
  `.env.example`; `LLM_BASE_URL` points at any OpenAI-compatible endpoint, OpenRouter by
  default) — the key is *access*; which model judges, **how it is sampled** (temperature,
  output budget, whether it may reason) and which prompts it is asked are pinned in the
  assessor's code and declared in its `SOURCE_CONFIG`, prompts fingerprint included, so
  changing any of them without a VERSION bump is refused at ratification. Sampling is
  identity because it decides the answer: `drafts-hybrid:2` exists because v1 asked a
  reasoning model for an answer inside a budget its thinking consumed whole, and got
  nothing back — see *Reading a calibration trace*. Every `evaluate` — dry run
  included — spends real calls (a few per evaluation; tasks are memoized per profile, and
  tokens/latency/`clean_retries` come back as `llm_*` metrics with the outcomes). When a
  task irrecoverably fails (transport down, output contract never satisfied, a
  degeneration that survived its one clean-conversation retry), the criteria it feeds
  degrade to **`execution_error`** — a fact of the run, never of the content, carrying its
  cause `{task, kind, message}` — and the rest of the evaluation persists (ADR-0037).
  Past the **failure budget** (a quarter of the criteria mapped for execution) the run
  was not an evaluation: it aborts whole and persists nothing; fix or just retry.
  `LLM_TIMEOUT_SECONDS` bounds one call before the transport treats it as transient and
  backs off — access like the key, so raising it for a long prompt against a slow provider
  re-versions nothing. The test suite never touches the network: the transport is faked at
  the `runtime.get_client` seam.
- **The calibration page** (`/admin/calibration` in the console) is the guided way to run
  the dry-run loop: pick a profiled content, an instrument version (drafts included) and
  an assessor package, run, and read the outcome table with quotes, claim statuses and
  LLM spend. It sits on `GET /admin/assessor-packages` (the in-code registry as data) and
  on the dry-run's three: `POST /admin/evaluations/preview` **starts** a run and returns
  its id (202), `GET /admin/evaluations/preview/{run_id}` reads it while it advances —
  one step per executed criterion and per LLM attempt, then the result or a named error —
  and `.../trace` returns every LLM attempt whole, prompts and raw answers included. It
  is the same `PreviewEvaluation` use case the CLI wires (accepts drafts, needs no
  ratification, persists nothing); it is started rather than awaited because with
  LLM-carried criteria it takes minutes. Runs live **in memory**, last few only: a
  restart forgets them, which is the correct trade for a dry-run that persists nothing.
  The CLI (`evaluate --dry-run`) stays as the scriptable path. What the page deliberately
  does **not** do: trigger profiling (a deliberate act, CLI-only — it shows the command
  instead) or register local folders (`register-package --source <dir>`). An
  LLM-carrying assessor spends real calls per run, on the backend's `LLM_API_KEY`.

### Evaluating a study in batch

A generation of the optimization experiment is a whole study's worth of courses, which is
one command (ADR-0040):

```
uv run python -m app.cli evaluate-study --study-id <id>
                                        [--assessor <name>:<version>]
                                        [--concurrency N] [--re-evaluate]
```

**The study decides the assessor** (ADR-0042): it pinned one before it opened, and the run
uses it. `--assessor` is optional and is *checked* rather than obeyed — passing one that
disagrees with the pin is refused, so a script written before the pin keeps working and a
mismatch is stated instead of silently resolved.

**Progress goes to stderr, the summary to stdout** — one JSON document naming every course
with its `briefId`, its status, its duration and what it spent, which is what a script reads
to know how a generation went. The statuses mean:

| status | what happened |
|---|---|
| `evaluated` | the course was judged and its evaluation persisted |
| `skipped` | this assessor had already evaluated it under this instrument version |
| `failed` | this course could not be judged; `cause` says why, and the others carried on |
| `cancelled` | the run stopped before reaching it; nothing was written for it |

**It refuses before it spends.** A study that is not open, no instrument pinned, no assessor
pinned, an empty dataset, an assessor that is unregistered or has not ratified the pinned
version, or a `--assessor` that disagrees with the pin: each would
fail identically for every course, so the command ends with the cause named and nothing paid
for. The same reasoning applies while it runs — a configuration failure, a coverage bug or
any failure this loop cannot place (a database one migration behind, say) ends the batch on
the first course, and three consecutive transport deaths end it too (any course that
completes clears that streak). A run that ends this way reports `failed` and names the course
that met it; `cancelled` is reserved for a human stopping it, because only one of the two is
a reason to go looking for a cause.

**Re-running resumes it.** What this assessor already evaluated is skipped, so a batch
interrupted at course twelve of twenty is continued by running the same command again.
`--re-evaluate` asks for all of them regardless.

**Ctrl-C stops it**, and stopping means *stop starting*: courses that finished stay
persisted, the ones in flight stop at their next call, and the summary still prints. Nothing
needs undoing — an evaluation that does not reach its end writes nothing.

**How much it asks for at once.** `--concurrency` is how many **courses** run at a time
(default `LLM_MAX_CONCURRENCY`). How many **requests** may be in flight is bounded by
`LLM_MAX_CONCURRENCY` at the transport itself, whatever the callers do, so nested fan-outs
can never multiply into a burst nobody chose. Default 4; raising it past ~7 also needs the
database pool raised, since each worker uses up to two sessions. If the endpoint pushes
back, the transport already backs off on 429 honouring `Retry-After` — the first real batch
is how the account's actual limit gets measured, rather than guessed.

**The same batch from the console.** `/admin/studies/<id>` carries an *Evaluation* card with
the identical work behind it — one use case, two doors, so they cannot answer differently.
It opens on the **durable** count ("12 of 20 courses judged"), which is a query over the
judgments rather than a run's memory: it is still right after a restart, and it counts a
batch someone ran from a terminal. Starting states what it commits to before asking, and
only offers assessors that have **ratified the pinned version** — the option that would be
refused is not shown. While it runs, the page reads it once a second (`POST
/admin/studies/{id}/evaluations` returns a run id; `GET …/{run_id}` reads it; `POST
…/{run_id}/cancel` stops it), showing a row per course, the current activity and a range for
what is left. A run is refused with **409** while another one over the same courses is alive:
two batches over one course would decide by arrival order, since every reader takes the most
recent judgment.

What the console cannot do, on purpose: watch or cancel a batch started from the CLI. They
are different processes and runs live in memory — the durable count reflects it all the same.
Runs are forgotten on restart; what they wrote is not.

### Reading a calibration trace

A semantic criterion's verdict is only as good as the question that produced it, and the
question is a prompt nobody sees. `LLM_TRACE_DIR` is where every attempt gets written —
one JSON object per line, per run:

```
{"task_id": "...", "attempt": 1, "model_requested": "...", "model_answered": "...",
 "provider": "...", "sampling": {...}, "messages": [...], "response_text": "...",
 "finish_reason": "...", "tokens_in": 0, "tokens_out": 0, "latency_ms": 0, "error": null}
```

One record per **attempt**, not per successful call: a task that took three rounds to
satisfy its output contract wrote three lines, and the second line's `messages` end with
the validator's own complaint about the first. Nothing is truncated — an abridged prompt
cannot be compared against the one that produced a different answer, which is the only
reason to read this.

What each field settles:

- `sampling` — what was asked for besides the conversation: temperature, the output
  budget, the response format, whether the model may reason. It decides the answer as
  much as the prompt does, so it is recorded next to it; `drafts-hybrid:1` failed every
  run on this half with its prompts intact.

- `finish_reason: "length"` with **no content** — the model stopped at the token limit
  having written nothing. A reasoning model bills its thinking as output tokens, so
  `max_tokens` is a budget the thinking can spend entirely; compare `completion_tokens`
  against `completion_tokens_details.reasoning_tokens` in the raw body to see it. The
  remedy is the task's budget or its `reasoning` setting, never a retry — the limit
  produces the same answer every time. This is what `drafts-hybrid:1` lost every run to.
- `provider` — OpenRouter routes one model id to several upstreams, and they differ in
  whether they reason and in how they honor `response_format`, so two runs asking the
  same question can get different shapes back. This is who answered.
- `error` with no `response_text` — the request never landed (timeout, rate limit). The
  next line is the retry.
- `error` mentioning **upstream** — the gateway answered 200 and the provider behind it
  failed. Treated as transient: the next attempt usually lands somewhere else.

Both doors write one: the page's runs under their run id, `evaluate --dry-run` under
`cli-<id>`, printing the path when it finishes. The folder is gitignored and disposable
— the traces of a machine, not of the repo. Leave `LLM_TRACE_DIR` empty and none are
written.

### What repeated runs tell you

One trace shows whether a question was answered. Only **repeats of the same content** show
whether the answer means anything, and they are the cheapest diagnostic available: run one
draft three times and compare the verdicts criterion by criterion. Four things that
measurement settles, none of them obvious from a single run.

- **Where the model disagrees tells you whose defect it is.** If repeats quote the same
  passages and describe the same facts, then split on the verdict, the criterion never said
  where its threshold is — and the fix is prose in the instrument, not a better prompt. If
  repeats disagree about *what the text says*, that is the judge, and only then are prompts,
  models or sampling the answer. Read the reasons side by side before touching anything.
- **Writing the missing threshold beats sampling.** Voting reduces variance, and an
  under-specified criterion is not variance: it is two defensible readings of one sentence,
  and a vote just picks one of them more consistently. Fixing the text removes the
  disagreement instead of averaging it.
- **Borderline instances belong to (content, criterion) pairs, not to criteria.** A criterion
  can be unanimous on one draft and a coin flip on the next, and one that looked settled over
  several observations can still turn. So there is no list of "hard criteria" to sample
  selectively — sampling, when it is used, applies to all of them.
- **A judgement is only diagnosable because it is quoted.** Every distinction above comes
  from comparing the passages and reasons of different runs. A bare verdict shows a number
  moving and nothing about why, which is the reason the output contract demands evidence at
  all (ADR-0009).

A judged criterion reports how close its vote was, as a
`judgment_agreement_<task>` metric of `{samples, agreed}`. Treat a criterion that keeps coming
back **2-1 as a bug report about the instrument**, not as noise to average away — that is the
signature of the first case above.

Two more signals ride with every task's `llm_*` metric since ADR-0037. `clean_retries`
counts the fresh conversations an answer cost: verdicts that needed one are a shifted
population — the retry changed the conversation that produced them — so compare them apart
before reading agreement across runs. And a criterion carrying `execution_error` names in
its cause `{task, kind, message}` exactly which task failed and how; a recurring
`degeneration` on one (content, criterion) pair is a bug report about the question, the
same way a recurring 2-1 vote is.

And the limit worth stating: self-agreement is not correctness. A criterion can be perfectly
stable and stably wrong, and nothing in these runs would show it. Only a human reading the
verdicts against the content can.

## Registering courses

The canonical intake is **discovery** (ADR-0027): declare a package source and the system
reads the artifact list, the descriptor and a content hash from the package itself. A course
declares which generator produced it, so the generator has to exist first — two acts, because
the name is typed once per generator and never again (ADR-0031):

```bash
# the lineage. A name one or two edits from a registered one is refused until you echo the
# name it named back with --distinct-from, which is what stops a typo minting a second one.
uv run python -m app.cli register-generator --name learnpack-generator

# a version under it, by id or by name; neither form ever creates the generator
uv run python -m app.cli register-generator-version   --generator-name learnpack-generator --version 2.4.0 --changelog "What changed."
```

```bash
# one course, by URL or by a local directory under the repo's courses/ tree
uv run python -m app.cli register-package --source https://my-course.learn-pack.com --generator <uuid|unknown>
uv run python -m app.cli register-package --source ../courses/unknown/my-course --generator unknown

# a course in any other package format — `--format` defaults to LearnpackV1
uv run python -m app.cli register-package --source ../courses/gen@2.0.0/a-run --generator <uuid> --format LearnpackV2

# every course under courses/<name>@<version>/ and courses/unknown/ (batch)
uv run python -m app.cli register-package --all
```

`--format` names the source's `PackageFormat` and **defaults to `LearnpackV1`**, so a package
in any other format needs it spelled out — discovery would otherwise read it with the wrong
adapter and refuse it. `--all` takes one `--format` for the whole tree, so a `courses/` tree
holding more than one format is registered one format per run.

Local sources need the dev API running (`AUTH_MODE=local`): it serves the repo's
gitignored `courses/` tree at `/packages` (base URL: `LOCAL_PACKAGES_BASE_URL`, default
`http://localhost:8000/packages`), so registered **locators** are fetchable http URLs —
brief intake and profiling then work exactly as with remote packages. That is all the mount
gives them: a local course registers with **no `consumable_url`**, because serving a
package's bytes is not deploying a course (ADR-0028). Pass `--consumable-url` only if the
course really is deployed somewhere a human can open it; without one it can be evaluated
automatically but not assigned for human scoring.
Re-importing an unchanged course is a no-op (content hash); the same declared version with
changed content is refused. See `../courses/README.md` for the folder convention.

### From other trees, and from the console (ADR-0035)

A tree that does not live under `courses/` is declared in the environment, because a
registered locator has to stay fetchable and only a served tree provides that:

```bash
# one tree, which you decide to call `runs`
LOCAL_SOURCE_ROOTS=runs=D:\generator\out
# two trees, comma-separated
LOCAL_SOURCE_ROOTS=runs=D:\generator\out,archive=/srv/old-courses
```

Each entry is `<name>=<folder>`. The name is yours to choose, but it is not a label: it
becomes the URL prefix the tree is served at (`LOCAL_SOURCES_BASE_URL/<name>/…`) and is stored
inside every locator registered from it, so renaming it strands the courses already
registered. It must match `[a-z0-9._-]+` and cannot be `courses` — that is the built-in root,
which keeps its own base URL forever. A malformed entry stops the process; a folder that does
not exist is reported as absent and skipped. Adding a root needs a restart, because the trees
are mounted when the app assembles.

Every declared root is browsable from **`/admin/contents/import`** in local mode: pick the
format and generator version once, walk to the folder that holds the courses, and the scan
says per subfolder what registering would do — `new`, `new_version`, `unchanged`, `conflict`
or `unreadable` — before anything is written. The CLI stays the batch tool for `courses/`,
and the `<name>@<version>/` folder convention is its own: the console declares the generator
in the form instead, and applies it to the whole scan.

One thing the console cannot do, and says so: re-registering a course that was registered
with an unknown generator does **not** fill it in. That registration is a no-op (the bytes
match), so the declared generator is discarded — attribution is its own act, offered on the
row (ADR-0024).

Registering **auto-profiles** each newly created course, once the format's extraction is
accepted — the same policy the admin form triggers (ADR-0029 §1). Both commands print what
it did (`profiling: N profiled, N failed, N not profiled`), because a decline is silent by
design and a failure is only logged. The batch therefore costs roughly one fetch per lesson
per created course; a large tree takes minutes, and there is no way to opt out yet.

`import-learnpack --file courses.json` remains for hand-composed batches that already
carry their artifact lists (canonical JSON shape only). With `--base-dir` its locators are
filesystem paths, so the automatic policy declines them; without it they are URLs and it
profiles like any other path.

## Adding a package format

A *package format* is a packaging convention this system knows how to read (e.g.
`LearnpackV1`). Supporting a new one means writing two or three small adapters against
existing ports, plus a handful of recorded human acts. You never touch the domain model,
the evaluation pipeline, the frontend, or the database schema.

**Concepts you need (30 seconds).** A *port* is an interface the core defines
(`FormatPackageDiscoveryPort`, `ExtractionAdapterPort`, `FormatBriefIntakePort`); an
*adapter* is your implementation of it for your format; a *registry* is the dict that maps
format name → adapter — adding a format is one new entry, never a wiring change.
Everything downstream of the `ContentProfile` (the canonical representation your
extraction adapter produces) is format-agnostic and does not change. The steps below land
**incrementally**: after step 2 your packages already register and dedupe; profiling and
evaluation come later.

The contract every format must satisfy is executable:
`tests/test_format_contract.py`, parametrized over `tests/format_cases.py`. A format
registered in any registry without a `FormatCase` fails the suite — so the kit is also
your to-do list: add your case early and work until it is green.

### Step 0 — Choose the format name. Carefully.

The string (e.g. `LearnpackV2`) is the namespace of every `externalId` (ADR-0005) and
travels into immutable rows: persisted profiles, published study reports. There is no
rename. This is the step with the least code and the most consequences.

### Step 1 — Freeze a real fixture package

Copy one real, representative package into `tests/fixtures/<your_format>/`. The fixture
comes first, not last: every later step is verified against it, and the contract kit
requires it. Prefer a package that exercises the format's full surface — every artifact
kind, and the commission if the format carries one (see the `FormatCase` fields).

### Step 2 — Discovery adapter (required; makes the format registrable)

File: `app/modules/evaluand_registry/infrastructure/package_discovery.py` — add your
class beside `LearnpackV1Discovery`, and one entry to the tuple that builds
`DISCOVERIES_BY_FORMAT` at the bottom of the file. Implement
`FormatPackageDiscoveryPort`: given a `PackageRoot` (an injected "place to fetch files
from" — filesystem or HTTP, you don't care which), read your format's manifests and
return a `DiscoveredPackage`: external id, title, the artifact list, and the content hash
(use the module's `_content_hash` helper — the hash scheme is a compatibility contract).

Rules that are easy to miss:

- Discovery is **hard-failing** by design (ADR-0027): if a manifest is missing or lies,
  raise `PackageDiscoveryError` — a mis-discovered package would *be* the evaluand,
  wrong. The one allowed soft spot is the commission artifact (LearnpackV1's carrier is
  its syllabus), whose absence is a recorded state.
- Discovery is the **sole writer of the artifact `kind` vocabulary** for your format.
  Your extraction adapter (step 3) will read exactly these kinds.
- Never mint a `consumable_url` yourself: ask the root (`root.consumable_url`). A
  filesystem root never declares one (ADR-0028 — serving bytes is transport, not
  deployment).

**You can stop here and ship.** After this step: the format appears in
`GET /admin/contents/formats` and in the admin form's selector; `register-package --format
<name>` works; re-imports dedupe by content hash; the brief registers absent; profiles are
simply not built yet. In your `FormatCase`, `expected_capabilities=None` says exactly this —
the extraction tests skip instead of failing.

To try it against a real course you need a generator to declare, which step 6 only registers
later. Declare `--generator unknown` instead: the state is a legitimate declaration and it is
repairable — `attribute-generator` links the course once the lineage exists, exactly once
(ADR-0024).

### Step 3 — Extraction adapter (required for any evaluation)

Directory: `app/modules/content_profiling/infrastructure/adapters/` — one module per
format, plus one entry in `ADAPTERS_BY_FORMAT` (`adapters/__init__.py`). Implement
`ExtractionAdapterPort`: read the registered artifacts and produce the entries of the
`ContentProfile`. Declare:

- `PACKAGE_FORMAT` — the same string as step 0. The two modules deliberately do not share
  the constant (module isolation); the contract kit checks they agree.
- `ADAPTER_VERSION` — the identity of *how you read*. Any change in the mapping is a new
  version, and each version needs its own acceptance (step 6).
- `CAPABILITIES` — which `DataRequirement` ids you can supply, chosen from the ids the
  instrument mints (`../docs/seed/instruments/`). Do **not** invent data your format does
  not declare: an unmet requirement correctly derives `not_applicable`, and
  matching/readiness surface it. Every value you produce must satisfy the requirement's
  declared `value_domain` (ADR-0020) — the profile aggregate verifies this when built.
- Extraction is deterministic and fails whole (`ExtractionError` → a `failed` profile),
  never half-profiles.

### Step 4 — Brief intake (only if your format carries the commission)

File: `app/modules/evaluand_registry/infrastructure/brief_intake.py`. If your packages
embed the instruction they were generated from (LearnpackV1:
`.learn/initialSyllabus.json`), implement `FormatBriefIntakePort` and register it in
`BRIEF_INTAKES_BY_FORMAT`: `locate()` finds the artifact, `derive()` turns its bytes into
a `DerivedBrief`. Intake is best-effort and non-blocking (ADR-0022): any miss logs and
registers the brief absent — a valid state, not an error. If your format carries nothing,
skip this step entirely; skipping is correct.

A commission is written by a person, so **what carries it is structured and what it says is
not**: both formats wrap free prose (LearnpackV1 in a syllabus field, LearnpackV2 in a
`{"content": …}` envelope). Parse the carrier, then leave the instruction alone — reading
fields out of the prose would substitute your reading for the creator's words. If the
carrier is ever plain text with no envelope at all, `derive()` has to say for itself what
"not a commission" looks like, because there is no parse step to fail it; the kit probes
that case.

Hash the **instruction**, not the payload: a brief's identity is what was asked, so the
same request re-wrapped must not mint a second one.

### Step 5 — Make the contract kit green

Add your `FormatCase` to `tests/format_cases.py` (fixture path + expectations, written as
literals — importing them from your adapter would make the assertions tautological). Run
`uv run pytest tests/test_format_contract.py`. The failing tests are your remaining to-do
list; when they are green, the code side is done. Behavior beyond the contract — your
format's equivalent of LearnpackV1's activity counting — gets its own test file, plus
calibration pins if any criterion depends on empirical thresholds
(`../docs/MEASUREMENT.md`).

### Step 6 — The recorded human acts (no code)

These are deliberate human decisions (ADR-0012, ADR-0019, ADR-0031); do not script them
away.

1. **Register the generator lineage and version** (once per generator — see
   [Registering courses](#registering-courses)). The spelling of the name is permanent;
   the version's changelog is write-once.
2. **Accept the extraction** (per adapter version): `accept-extraction --package-format
   <name> --email <admin>`. This is what arms auto-profiling on registration; until then
   profiling stays manual.
3. **Bind the instrument to the format**: add a `bindings` entry with your
   `package_format` (see `../docs/seed/instruments/learnpack-course-qa-v1.yaml`). A
   published version is immutable, so this means a new instrument version
   (`bump-instrument` → edit → `import-instrument` → `publish-instrument`). Then check
   `GET /admin/instruments/{version}/matching?package_format=<name>` for the demand your
   format cannot meet — those criteria derive `not_applicable`, which is honest, not
   broken.
4. **Ratify the assessor for the new instrument version** (ADR-0019, command — or the
   `/admin/assessors` button — under
   [Instruments and content profiling](#instruments-and-content-profiling-slice-2)).
   Criteria the assessor cannot execute derive `not_assessed` — the visible backlog, not
   a failure.

### Step 7 — Verify end to end

`register-package` → auto-profile (or `profile-content`) → `evaluate --dry-run` while the
instrument is a draft → `declare-study` (name it, and choose its instrument, judge and
briefs then or later with `update-study`) → `open-study` (**this is what pins the triple**)
→ `evaluate-study` (the whole dataset in one run) → `show-preview` (what signing off would
write, readable before the irreversible act) → `sign-off-study` →
`show-report` / `show-fitness`.

### What you never touch

Domain and application layers of any module · the ports · the events · the assessors'
logic · the frontend (the form reads formats from the API) · migrations. If a step seems
to require touching one of these, stop: either the step is wrong or it needs an ADR
first.

**What you may well touch:** `app/cli.py`. It is the composition root, and the local intake
path in it has been written against one format at a time before. A helper that names a
specific format's file is a bug the next format uncovers, not a rule you have to work
around — fix it there.

## Authoring an instrument

An *instrument* is the **evidential argument** a study pins: what is being asserted about a
generator's output, and what would count as evidence for it. Adding a package format teaches
the system to *read* something; authoring an instrument decides what is worth *asking*.

Authoring is file-based and assistant-drafted, publishing is a human act, and a published
version never changes. The commands are in
[Instruments and content profiling](#instruments-and-content-profiling-slice-2) — that table
decides which one you want. This runbook is about what to write.

**The chain, in one line.** A **quality** is what we care about · a **claim** asserts one
thing about **exactly one** quality (ADR-0026) · a **criterion** is a check whose outcome
evidences a claim · a **data requirement** is a datum a criterion needs to be executable, and
an extraction adapter is what supplies it. You author from the top down and the system
validates from the bottom up.

There is no aggregate score across criteria and there never will be (ADR-0011). An instrument
reports per criterion, per claim; anyone looking for one number is looking for a different
system.

### Step 0 — Do you actually need a new instrument?

Usually not. **An instrument forks when its claims change, not when the package format
changes** (ADR-0032). A new format normally joins the instrument you already have: add a
`bindings` entry, publish the new version, done.

Criteria the new format's extraction cannot feed derive `not_applicable`. That is a report,
not a defect — demand stated honestly and left unanswered — and it is not a reason to fork.

Measure it before deciding:

```bash
GET /admin/instruments/{instrument_version_id}/matching?package_format=<name>
```

It returns, per criterion, what it requires and what is missing; the unmet demand grouped by
data requirement; and per claim, how many of its criteria are covered. **A claim with zero
covered criteria is the signal to read closely**: either the format cannot answer a question
that still applies, or the question does not apply to that artifact at all. The second case is
where a second instrument is warranted — and what justifies it is the different question, not
the different format.

### Step 1 — Know what you cannot mint here

Qualities, dimensions and frameworks are **reference data**, not instrument content. They live
in `../docs/seed/pedagogical-reference.yaml` and enter with `uv run python -m app.cli seed`.
Your instrument *references* their ids; publishing refuses ids that do not exist.

So if your argument needs a quality nobody has named yet, that is an edit to the reference
file and a reseed — before you publish, not during. The same goes for a warrant: a claim can
only cite a framework the reference declares.

### Step 2 — Reuse data requirement ids; mint only what is new

The demand-side namespace is **global across instruments** (ADR-0014). A criterion may require
an id that already exists without redeclaring it in your file — inheriting `lesson_bodies` or
`course_descriptor` costs nothing and keeps one meaning per id.

Declare a `data_requirements` entry only for an id you are **minting**, and write its
`definition` and its `value_domain` at that moment: the definition says what the datum means,
the value domain says what shape it takes, and both are the contract extraction adapters
conform to (ADR-0020).

Redeclaring an existing id with a different definition or a different shape is blocked by a
lint. That is the guardrail, not an obstacle — decide which case you are in:

| Situation | What to do |
|---|---|
| Same meaning, different words | Keep the existing definition, or add an `aliases` entry |
| Same meaning, the declaration itself is wrong | `import-instrument --revise-definitions`, the deliberate act |
| Similar but **not** the same thing | Mint a new id with its own definition |

One constraint that bites from the other side: **an extraction adapter cannot declare a
capability for an id no instrument declares.** The format contract kit asserts
`capabilities ⊆ declared_value_domains()`. So a datum and its supply land together — mint the
id in the instrument and teach the adapter to produce it in the same change, or the kit
refuses one half of it.

### Step 3 — Write the YAML

One file per version, `../docs/seed/instruments/{instrument_id}-{version}.yaml`.
`learnpack-course-qa-v1.yaml` is the worked example to read alongside this.

| Key | What it carries |
|---|---|
| `instrument_id`, `version`, `name`, `purpose` | The identity and what the argument is for |
| `assisted_by` | What drafted it and in what role — assistance is recorded, never hidden |
| `bindings` | The `package_format`s this version is designed for, plus `task_variables` a criterion conditions on (demand-driven: add one when a criterion needs it, not before) |
| `data_requirements` | Only the ids you mint (step 2) |
| `claims` | `statement`, one `qualities` entry, `warrants`, `sufficiency`, `alternative_explanations` |
| `criteria` | `statement`, `pass_condition`, `failure_modes`, `claims`, `requires`, `on_missing_evidence`, `eligible_sources` |

Four things that are easy to write carelessly:

- **`alternative_explanations`** on a claim is the discipline that keeps a `fail` honest: what
  else could produce this evidence besides the defect you are asserting? Write the ones a
  dispute would raise.
- **`on_missing_evidence`** decides what a criterion does when its datum is absent. `fail`
  says the absence **is** the finding (ADR-0021 records it as derived, with no quote);
  `no_evidence` says absence settles nothing. Choosing `fail` is a claim in itself — make it
  deliberately.
- **`pass_condition` and `failure_modes` are read by more than people.** An assessor that
  judges with an LLM puts them **verbatim into the model's prompt**, so they have to stand on
  their own: no criterion ids, no file names, no "that is handled elsewhere". A model has no
  referent for those and, told about a neighbouring concern, will reason about the thing it
  was asked not to judge. State an exclusion in its own terms — *"naming what comes next is
  not teaching it"* — and stop there; the cross-reference belongs in a YAML comment, which
  never reaches the model.
- **The criteria of one claim must not contradict each other.** `sufficiency: conjunctive`
  means every criterion has to pass, so if one passage can fail one criterion for being
  present and another for being absent, that claim is **unsatisfiable** for that shape of
  content — and no evidence will ever fix it. Read a claim's criteria together, against a
  real example, before publishing. This is not hypothetical: `cl-course-closes-by-integrating`
  shipped with exactly that defect and it took an LLM oscillating between the two readings to
  make it visible.

`sufficiency` today has one built rule: `conjunctive`. `existential` and `m_of_n` are
documented vocabulary, not behavior — do not author against them yet.

### Step 4 — Import, then make publish green

```bash
uv run python -m app.cli import-instrument --file ../docs/seed/instruments/<file>.yaml
uv run python -m app.cli publish-instrument --id <version-id> --email <admin>
```

`import-instrument` creates or replaces a **draft** and runs the lint: data requirements
well-formed, no divergent redeclarations, no criterion requiring an id nothing defines. It
reports every problem in one run rather than stopping at the first.

`publish-instrument` validates the **whole evidential argument**, and that list is this
runbook's equivalent of the format contract kit — the executable definition of a complete
instrument:

- every criterion references a claim that exists;
- every criterion's required data is inside the namespace;
- there is at least one claim;
- every claim has at least one criterion evidencing it;
- every claim asserts about **exactly one** quality (ADR-0026);
- every quality and every warrant a claim cites is known reference data;
- there is at least one `bindings` entry.

Iterate on the draft as often as you like — it is replaced in place, no version bump involved.
Publishing is the point of no return: from there the version is immutable and any change is a
new version (`bump-instrument`).

### Step 5 — The recorded human acts

1. **Publish** — the act above. Nothing assistant-drafted reaches published without a human
   performing it.
2. **Ratify the assessors** against this instrument version (ADR-0019), from the CLI or from
   `/admin/assessors` (ADR-0036 — the page shows the text of each criterion whose decision
   the act is waiting for). Within one lineage
   this is cheap — the diff against the previous version is computed mechanically and only
   changed or new executed criteria need `--confirm`. Across instruments it is not a diff at
   all: an assessor vouched for one argument has not been vouched for another, so a new
   instrument ratifies from scratch. Criteria no assessor can execute derive `not_assessed` —
   the visible backlog, not a failure. There is no un-ratify: if the decision was wrong, the
   exits are a new assessor version or a new instrument version.

   One prerequisite the act cannot supply: a **new lineage** can ratify nothing until an
   assessor artifact declares itself against it — coverage is code, not an act. The
   declaration is the package's `INSTRUMENT_ID`
   (`app/modules/evaluation/infrastructure/assessors/<name>/__init__.py`), and
   `ratify-assessor` refuses a package whose `INSTRUMENT_ID` names another lineage. Writing
   that package is the prerequisite; ratifying it is the human act.

### Step 6 — Verify end to end

Calibrate while it is still a draft — `evaluate --content-id <id> --instrument-version-id <id>
--assessor <name>:<version> --dry-run` persists nothing and prints the outcome table, so you
can read what your criteria actually do against real content before freezing them. It is also
the **only** way to exercise an instrument whose lineage has no assessor yet: the dry run does
not compare lineages, so any registered package's executors can be pointed at any version.
Then the study path:
`declare-study [| update-study] | open-study` →
`evaluate-study` → `show-preview` → `sign-off-study` → `show-report`.

### What you never touch

A published version, ever — bump instead · the qualities and frameworks from inside an
instrument file — they are reference data (step 1) · the meaning of an existing data
requirement id without `--revise-definitions` · the domain rules publish enforces. If your
argument seems to need one of these bent, it needs an ADR first.

## Modules

identity · evaluand_registry · evaluation_design · content_profiling · evaluation ·
orchestration · golden_dataset · reporting. Each with `domain/`, `application/` and
`infrastructure/`, and its contract in `public.py`.

The plans that originated them are frozen in `../docs/design/08-code.md` (slice 1) and
`../docs/design/13-code-qa.md` (slice 2); progress lives in `../STATUS.md`.
