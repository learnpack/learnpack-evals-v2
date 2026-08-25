# backend

FastAPI + Postgres. Design lives in `../docs/` — **it is the source of truth**.
Hard rules: `../docs/ARCHITECTURE.md`. Names: `../docs/GLOSSARY.md`.
Where development stands today: `../STATUS.md` (this README describes **how it works**, not
what state it is in).

**Just want to measure a generator's output?** `../docs/RUNBOOK-measuring.md` is that guide,
and it does not need this file.

## Where to look

| You want to… | Read |
|---|---|
| run it on your machine | [Setup](#setup) |
| find a command or a setting | [Commands](#commands) · [Configuration](#configuration) |
| understand the code's shape | [Code shape](#code-shape) |
| register courses | [Registering courses](#registering-courses) |
| run a round and read its result | [Evaluating](#evaluating) |
| deploy an instance for an SME campaign | [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| make a batch bigger or faster | [`TUNING.md`](TUNING.md) |
| teach the system a new package format | [`../docs/RUNBOOK-adding-a-format.md`](../docs/RUNBOOK-adding-a-format.md) |
| write or revise an instrument | [`../docs/RUNBOOK-authoring-an-instrument.md`](../docs/RUNBOOK-authoring-an-instrument.md) |
| find out why a judge answered that | [`../docs/RUNBOOK-calibrating.md`](../docs/RUNBOOK-calibrating.md) |

## Setup

**This system is meant to be run on your machine.** Everything below — registering a
generation, judging it, reading the score — happens against a Postgres container and needs no
accounts and no cloud. A deployed instance exists for one errand, putting courses in front of
subject-matter experts, and is [its own job](#a-deployed-instance).

From the repo root, with Docker, [Task](https://taskfile.dev/installation/),
[uv](https://docs.astral.sh/uv/) and Node 20+ installed:

```bash
task setup     # once: env templates, dependencies, Postgres, migrations, seed + workbench
task dev       # daily: the containers, the API on :8000, the console on :3000
```

`task --list` has the rest; the ones worth knowing:

| Task | |
|---|---|
| `task db:reset` | destroy the local database and rebuild it from zero — volume, migrations, workbench. It asks first |
| `task seed:demo` | add the human panel's demo on top: two evaluators, two frozen courses, an open campaign ([below](#local-mode-and-clerk-mode-adr-0008)) |
| `task backend` · `task frontend` | one server at a time, when you do not want both |
| `task db` · `task db:down` | the Postgres containers alone; `db:down` keeps the dev volume |

`GET /health` verifies that the API boots and the DB responds.

**The same setup by hand**, from `backend/`, when you want to vary a step or see what one did:

```bash
cp .env.example .env      # ships in local mode: nothing to fill in
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run python -m app.cli seed             # the human reference instrument + reference data
uv run python -m app.cli seed-workbench   # publish, accept, ratify, register (local only)
uv run uvicorn app.main:app --reload
```

`seed` installs the two things nothing in the app can author, both idempotent: the **human
reference instrument** (`../docs/seed/rubric-v2.json` — one Likert statement per quality, which
is how a panel of experts is asked, ADR-0052) and the **pedagogical reference data** — the
qualities, dimensions and frameworks an instrument cites, without which publishing one refuses.

### A deployed instance

Clerk, Neon, Render and Netlify come in for one reason: a human evaluation campaign, where SMEs
who do not have this repository open a course in a browser and score it. `.env` then needs
`DATABASE_URL` (Neon), the Clerk keys and `AUTH_MODE=clerk`, and it is done **once per instance**
in an order that cannot be improvised — [`ENVIRONMENT.md`](ENVIRONMENT.md) is that whole job.
Nothing else in this file needs it.

### The workbench: what makes a fresh database able to measure (ADR-0045)

Migrating and seeding leaves a database that holds no published instrument, vouches for no
extraction adapter and permits no assessor to judge — so `evaluate` refuses. Three acts fix
that, and all three are human acts by decision: publishing an instrument version (ADR-0012),
accepting a format's extraction (ADR-0012) and ratifying an assessor against a version
(ADR-0019).

`seed-workbench` **replays** them from `../docs/seed/workbench.yaml`, which declares the
instrument versions to publish, the formats to accept and the generator lineages to register.
It installs exactly what the manifest names, attributes every act to the local admin, and
**refuses outside `AUTH_MODE=local`** — what is replayed is the repetition, never the decision.
It is idempotent, so run it after every migration and every wipe.

Assessors, courses and generator **versions** are absent from the manifest on purpose: which
assessors exist is the code registry's answer (ADR-0016), and courses and generator versions are
facts about a run, read off the tree each generation is registered from
([Registering courses](#registering-courses)). To move a lineage forward: bump the instrument,
calibrate the new version with `evaluate --dry-run`, and change one line in the manifest.

**The schema is checked at both doors.** The API and the CLI compare the database's revision against
this checkout's head before doing anything. On your machine (`AUTH_MODE=local`) a mismatch **refuses
to start** and names the fix (`uv run alembic upgrade head`); on a deployed instance it logs a
warning and carries on, because a deploy may start a process while the migration step is still
running. The suite migrates its own database, so a green suite says nothing about the store you run
against — which is why the check exists. If the revision is one this checkout does not know, pull.

## Local mode and Clerk mode (ADR-0008)

`AUTH_MODE` decides where a request's identity comes from:

| Mode | Identity | Where |
|---|---|---|
| `local` | the `X-Dev-User: <email>` header, unverified | your machine — no accounts, no cloud. `.env.example` ships it |
| `clerk` (the code's default) | session JWT verified against the JWKS | a deployed instance, where real people sign in |

Below the claim **it is the same code in both modes** (`ResolveAssessor`, `assessors.role`,
`require_admin`): local mode does not fork business rules, it only replaces where identity comes
from — the same cut the test suite uses. So a flow rehearsed locally is the flow that runs
deployed, and the console has no second version of itself. Setting up the other mode, Clerk
against your own machine included, is [`ENVIRONMENT.md`](ENVIRONMENT.md).

The two share one database, and credentials cannot collide — a local assessor is stored as
`('local', <email>)` and a Clerk one as `('clerk', <sub>)`. What keeps the modes themselves from
mixing:

- A value that is neither `clerk` nor `local` **does not boot**: a configuration error, not a
  silent degrade.
- `AUTH_MODE=local` with `ENVIRONMENT=production`, or with a `DATABASE_URL` not pointing at
  localhost → **does not boot** either. Two checks because each covers the other's blind spot:
  `ENVIRONMENT` is a label nobody guarantees, the database host is a fact about where the data lives.
- In `clerk` mode the `X-Dev-User` header **is not read** — it is another adapter, not a fallback
  for a missing token. It *is* looked at to explain a 401, naming the mismatch and both files to fix.
- `seed-demo` and `seed-workbench` abort unless the mode is `local`. For the second the stake is
  larger than stray rows: it replays acts that are human ones by decision (ADR-0045 §2).
- `GET /dev/identities` — the list feeding the frontend's user picker — 404s outside local mode. It
  also offers the addresses **invited and never signed in**, marked `pending`, so the whole
  registration flow can be walked through with no accounts and no cloud (ADR-0049).

**`seed-demo`, the third seeder** (`task seed:demo`). `seed` installs what nothing can author and
`seed-workbench` makes the database able to **measure**; this one installs the **human panel's**
demo, so that the flow an SME campaign runs can be walked through locally, with no accounts and no
cloud: 3 users (`admin@local.dev`, `ada.lovelace@local.dev`, `grace.hopper@local.dev`), 2 courses
registered from their real frozen packages and profiled by an explicit step of its own (their
locators are relative to the fixture tree, and automatic profiling only reaches http(s) ones —
ADR-0029), and an open campaign with **quorum 2** and its 4 assignments. Two evaluators is the
minimum for inter-rater dispersion and for `ContentEvaluationCompleted → GoldenReferenceEstablished`
to fire. It goes through the real use cases, so it publishes the same events the console would.

`seed-demo --reset` **wipes the local dataset** — everything the app writes, `local|` users included
— and reseeds; it does not touch the rubric or the reference data. Deliberately wholesale rather
than scoped: editing `DEMO_ASSESSORS`/`DEMO_CONTENTS` is the normal way to shape a demo, and a
scoped delete strands everything the previous version created. `task db:reset` is the bigger hammer
— it destroys the database volume, so there is no list of tables to keep in step.

## Configuration

`.env.example` is the local template and carries the reasoning for every variable — copy it as-is
and the app runs. What you may actually need to change:

| Variable | For |
|---|---|
| `LLM_API_KEY` | assessors that carry an LLM. An **OpenRouter** key: access, never identity (ADR-0034). The one thing local mode cannot ship filled in |
| `LOCAL_SOURCE_ROOTS` | trees of generated courses outside `courses/` — [From other trees](#from-other-trees-adr-0035) |
| `TEST_DATABASE_URL` | where the suite runs — see [Tests and CI](#tests-and-ci) |
| `DATABASE_URL` | the store. The local container by default; Neon needs `?sslmode=require` |
| `LLM_TRACE_DIR` | where a run writes its prompts and raw answers; empty means no trace file |
| `BATCH_MAX_COURSES` · `LLM_MAX_CONCURRENCY` · `HTTP_MAX_CONCURRENCY` · `DB_POOL_SIZE` | how much is asked for at once — [`TUNING.md`](TUNING.md) |
| `AUTH_MODE`, `CLERK_*`, `ADMIN_EMAILS` | only a deployed instance — [`ENVIRONMENT.md`](ENVIRONMENT.md) |

## Commands

Every CLI command runs from `backend/` as `uv run python -m app.cli <command>`, and `--help` on
any of them is authoritative. What each one is *for*:

| Command | For |
|---|---|
| `seed` · `seed-workbench` · `seed-demo` | the human reference instrument and the reference data · what a database needs to measure · the human panel's demo (the last two, local only) |
| `invite-assessor` · `list-invitations` | register a human evaluator by inviting them ([`ENVIRONMENT.md`](ENVIRONMENT.md)) |
| `set-role` | break-glass role change, without the console's guardrails |
| `register-generator` · `register-generator-version` | the lineage, then a version under it |
| `register-package` | register a content version by discovering a package source |
| `import-learnpack` | hand-composed batches that carry their own artifact lists |
| `attribute-generator` · `declare-deployment` | a generator learnt after registration (once) · where a version is deployed (repeatable) |
| `delete-content` | remove a content version nothing has used — local development only |
| `profile-content` · `accept-extraction` · `reprofile` | read one package by hand · arm auto-profiling for a format · re-profile a format in batch |
| `import-instrument` · `publish-instrument` · `bump-instrument` | draft · the human act that freezes it · clone a published version into the next draft |
| `ratify-assessor` | make an instrument version evaluable by an automated assessor |
| `evaluate` · `evaluate-study` · `measure` | one content · every course of an open study · a folder, register to score |
| `dump-concept-touches` · `dump-concept-map` | the two calibration dumps ([`../docs/RUNBOOK-calibrating.md`](../docs/RUNBOOK-calibrating.md)) |
| `declare-study` · `update-study` · `open-study` | declare a round, shape it, then pin it |
| `show-preview` · `sign-off-study` | the report a study *would* publish · compose, freeze and sign it |
| `show-report` · `show-fitness` | the signed-off report · the fitness projection (ADR-0023) |

Development, from `backend/`:

```bash
docker compose up -d     # local Postgres: db (tests) + db-dev (development)
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy              # types (strict, scope in pyproject.toml)
```

## Code shape

Dependencies point inwards only. The full rules are `../docs/ARCHITECTURE.md`; this is the map.

| Folder | Layer | May import |
|---|---|---|
| `app/modules/*/domain` | Domain | no framework — **pure Python** |
| `app/modules/*/application` | Application | its own domain + `shared`; **defines the ports** |
| `app/modules/*/infrastructure` | Adapters | application + domain (repos, routers, ACLs, extraction adapters) |
| `app/platform`, `app/main.py` | Frameworks | everything; injects the dependencies |

**A module's public surface** (ARCHITECTURE.md §3). Each module exposes its contract in
`modules/<m>/public.py`: query DTOs, its event names, and a `get_<m>_queries` provider for
`Depends` injection that **builds its own repo inside**. Other modules import **only** from
there — never from another module's `infrastructure` (that couples them to the concrete adapter
instead of the port) nor from its `domain`. The sole exception is the composition root
(`main.py`, `cli.py`, `platform/`), whose job *is* to inject concrete adapters.
`tests/test_architecture.py` makes the rule executable, on every `pytest`, without a DB.

**Events-first** (ADR-0003). Publishing an event is an `INSERT` into `events` with the use case's
session, in the same transaction as the aggregate (`OutboxEventPublisher`). After commit, the
in-process `EventDispatcher` delivers it to subscribed policies, which must be idempotent by
`event_type + aggregate_id` so reprocessing from the table is safe. The wiring is one list in
`app/platform/policies.py`, called by both the API and the CLI so the two processes cannot drift
(ADR-0029 §1). `app/platform/uow.py` is the transactional boundary each use case receives:
`uow.commit()` commits and **then** dispatches the now-durable events.

**The policies wired today.** Registering content auto-profiles it **iff** the format's extraction
is accepted **and** every artifact locator is an http(s) URL — packages rooted on a filesystem are
declined in silence and stay on the manual path. And the human path's completion chain:

```
EvaluationSubmitted → (orchestration) ContentEvaluationCompleted
                    → (golden)        GoldenReferenceEstablished
```

`orchestration` marks `submitted` every open assignment of `(assessor, content)` whose campaign uses
the same `instrumentVersion` — so one evaluation can satisfy several campaigns — and publishes
`ContentEvaluationCompleted` at `COUNT(assignments submitted) ≥ required` (ADR-0002), in its own
transaction after the evaluation's commit: completion is **eventual**, not a transactional
invariant. Golden keeps no count of its own; it asks orchestration for coverage through its query
port and applies `coverage ≥ threshold`.

**Reporting** (ADR-0006) composes the other modules through their `public.py` and aggregates in
Python — no cross-module JOINs and no read-model tables. `GET /admin/reports/scores` gives each
course's per-criterion profile (average across assessors, plus inter-rater dispersion; **no
aggregate score across criteria**, ADR-0011) and `GET /admin/progress` who evaluated what,
cross-campaign. Two rules not to confuse: a **repetition** is the same assessor on the same
`(content, instrumentVersion)` and collapses to the most recent because it is a correction
(evaluating two different courses is not one); and dispersion with a single rater is `null`, not
`0`, because there is no agreement to measure.

## Registering courses

The canonical intake is **discovery** (ADR-0027): declare a package source and the system reads
the artifact list, the descriptor and a content hash from the package itself. A course declares
which generator produced it, so the generator has to exist first — two acts, because the name is
typed once per generator and never again (ADR-0031):

```bash
# the lineage. A name one or two edits from a registered one is refused until you echo the
# name it named back with --distinct-from, which is what stops a typo minting a second one.
uv run python -m app.cli register-generator --name learnpack-generator

# a version under it, by id or by name; neither form ever creates the generator
uv run python -m app.cli register-generator-version --generator-name learnpack-generator --version 2.4.0 --changelog "What changed."
```

Then the courses. Three ways of naming what to register, one act underneath:

```bash
# one course, by URL or by a local directory inside a declared source root
uv run python -m app.cli register-package --source https://my-course.learn-pack.com --generator <uuid|unknown>
uv run python -m app.cli register-package --source ../courses/unknown/my-course --generator unknown

# a course in any other package format — `--format` defaults to LearnpackV1
uv run python -m app.cli register-package --source ../courses/gen@2.0.0/a-run --generator <uuid> --format LearnpackV2

# every course under courses/<generator-folder>/, or of another declared tree
uv run python -m app.cli register-package --all
uv run python -m app.cli register-package --all --root generated --format LearnpackV2

# every course a file names, by URL
uv run python -m app.cli register-package --from-csv ./courses.csv \
  --generator-name learnpack-generator --generator-version 2.4.0 [--register-new-version]
```

`--format` names the source's `PackageFormat`, and **on `register-package` it defaults to
`LearnpackV1`** — a package in any other format needs it spelled out, since discovery would
otherwise read it with the wrong adapter and refuse it. (`measure` defaults to `LearnpackV2`
instead, which is what the generator writes today.) `--all` and `--from-csv` take one `--format`
and one generator for the whole run, so a tree or a file mixing two of either is two runs.

**The generator folder declares the version, and a new version is registered as it is read.** Two
conventions, tried in that order: `courses/`'s own `<name>@<version>`, and the `<name>-<version>`
a generator writes when it names its own output folder (`learnpack-generator-04a7dd5-dirty`). The
second cannot be split syntactically — the version carries hyphens of its own — so it is split
against the registry: the registered lineage whose name the folder starts with, and the rest is
the version. A **lineage** is never minted from a folder name (ADR-0031); a **version** is,
because it changes with every commit of the generator being measured.

**Local sources need the dev API running** (`AUTH_MODE=local`): it serves the repo's gitignored
`courses/` tree at `/packages` (base URL `LOCAL_PACKAGES_BASE_URL`), so registered **locators**
are fetchable http URLs and brief intake and profiling work exactly as with remote packages. That
is all the mount gives them: a local course registers with **no `consumable_url`**, because
serving a package's bytes is not deploying a course (ADR-0028). Pass `--consumable-url` only if
the course really is deployed somewhere a human can open it; without one it can be evaluated
automatically but not assigned for human scoring.

Re-importing an unchanged course is a no-op (content hash); the same declared version with changed
content is refused. See `../courses/README.md` for the folder convention, and
[`TUNING.md`](TUNING.md) for how much a registration fetches at once and what bounds it.

**Registering auto-profiles** each newly created course, once the format's extraction is accepted
(ADR-0029 §1). Both commands print what it did (`profiling: N profiled, N failed, N not
profiled`), because a decline is silent by design and a failure is only logged. A large tree
therefore costs roughly one fetch per lesson per created course, and there is no way to opt out
yet.

`import-learnpack --file courses.json` remains for hand-composed batches that already carry their
artifact lists (canonical JSON shape only). With `--base-dir` its locators are filesystem paths,
so the automatic policy declines them; without it they are URLs and it profiles like any other
path.

### A generation, from a list of URLs (`--from-csv`)

**The file is read forgivingly**, because what arrives is a spreadsheet somebody exported: the
**first column** of each row and nothing else, skipping a header row, blank lines, rows parked
behind a `#`, and duplicates. What is refused is an entry that is not `http(s)` — that is a course
this path would register wrong, and a local one belongs to `--source` or `--all`.

**The generator is declared once**, by id (`--generator <uuid|unknown>`) or by the friendlier pair
`--generator-name <lineage> --generator-version <version>`. The lineage is **resolved, never
created** (ADR-0031); the version **may** be created, but only with `--register-new-version`, and
without it an unregistered version stops the run before a single course is fetched. That is the
difference from `--all`, where the version is read off a folder the generator itself named: here a
typo would not mint one stray version, it would attribute the whole list to it — and content is
never retired (ADR-0033) while `attribute-generator` only fills an `unknown` and never corrects
one.

**Everything that would fail for every row fails once**, before the first fetch: the file, the
format, the generator. After that a course that fails is one line of the summary and the batch
carries on, and **re-running the same file finishes it**, because an unchanged package is a
reported no-op — which is also how *how far did it get* is answered, and why this stays a plain
foreground command rather than a run in the shape `evaluate-study` uses.

Ctrl-C stops it with nothing to undo, each course being its own transaction, but there is no SIGINT
handler here: it stops mid-course and prints no summary. A course interrupted between its commit
and its profiling stays unprofiled, and re-running the file will not notice, since an unchanged
package emits nothing — `profile-content --content-id` is the repair, exactly as for `--all`.

### Declaring the deployment of a registered course (`declare-deployment`)

A course registered from `courses/` declares **no** consumable URL — dropping a folder into a tree
deploys nothing (ADR-0028) — and **that is what decides whether it can be scored by a person**:
without one the console refuses it in the assign picker, so it can be judged automatically but
never handed to an SME. When the course *is* deployed afterwards, this points the registered
version at it:

```bash
# one course, or a spreadsheet of them: two columns, `external_id,url`
uv run python -m app.cli declare-deployment --external-id <id> --url https://<course>.learn-pack.com/ --email <admin>
uv run python -m app.cli declare-deployment --from-csv ./deployments.csv --email <admin>
```

**Which `external_id`.** It is the identity the package declares about itself, read off it by
discovery and never typed by hand — `/admin/contents` lists it in the first column, and
`register-package` prints it. What it is made of is the format's business:

| Format | `external_id` | From |
|---|---|---|
| `LearnpackV1` | the course slug — `introduction-to-generative-ai` | `slug` in `learn.json` |
| `LearnpackV2` | `<seed>-<run start UTC>` — `03-html-fundamentals-20260810184810` | `system_metadata.run_info.seed_id` and `started_at`, in `traces/run_metadata.json` |

LearnpackV2 composes it because neither half identifies a course alone: the seed says *which
instruction* was given and collides across regenerations, the timestamp says *which run* and says
nothing about what was asked. Both are the run's own declarations, so the id survives the tree
being moved, renamed or served from somewhere else — which the directory name, the other obvious
candidate, would not. It is namespaced by the format (ADR-0005), so `(format, external_id)` is the
logical course and the same string under two formats is two courses.

**It fetches nothing.** A `ContentProfile` is built from artifact locators and Content Profiling
never reads this field, so the evaluand keeps its identity, its `content_hash` and its profile —
the only thing that changes is whether a human can be handed the course.

The same act is `POST /admin/contents/{content_id}/consumable-url`. The console does not offer it
yet: `/admin/contents` shows a declared URL as a link and nothing more, so the CLI is the way in.

**Unlike `attribute-generator`, it may be repeated** (ADR-0054): an attribution is a discovery —
the fact was always true — while a deployment is a statement about the world right now, and courses
move. Every change is recorded with what it moved from and who moved it; declaring the URL a
content already has writes nothing; clearing one is refused.

The file is read as forgivingly as `--from-csv` reads its URLs. Two things are refused rather than
guessed: the same course named twice with **different** URLs, and an **id registered at more than
one version**, since which version is deployed is not something the id settles. Any failed row
makes the run exit non-zero, so a fifty-row file cannot half-succeed quietly.

### From other trees (ADR-0035)

A tree that does not live under `courses/` is declared in the environment, because a registered
locator has to stay fetchable and only a served tree provides that:

```bash
LOCAL_SOURCE_ROOTS=generated=D:\generator\datasets\generated,archive=/srv/old-courses
```

Each entry is `<name>=<folder>`. The name is yours to choose, but it is not a label: it becomes the
URL prefix the tree is served at (`LOCAL_SOURCES_BASE_URL/<name>/…`) and is stored inside every
locator registered from it, so renaming it strands the courses already registered. It must match
`[a-z0-9._-]+` and cannot be `courses` — the built-in root, which keeps its own base URL forever. A
malformed entry stops the process; a folder that does not exist is reported as absent and skipped.
Adding a root needs a restart, because the trees are mounted when the app assembles — which is also
one of the two things `--root <key>` names when it refuses a key: never declared, or declared after
the API started. `--root` works on `register-package` and on `measure`, and defaults to `courses`.

Every declared root is also browsable from **`/admin/measure`** in local mode, which is the page
the console is arranged around: declare the format and generator version once, walk to the folder
that holds the courses, and the scan says per subfolder what registering would do — `new`,
`new_version`, `unchanged`, `conflict` or `unreadable` — before anything is written. Ticking the
ones you want registers them, and the same page then opens the round over them. One thing the console cannot do, and says so: re-registering a course
that was registered with an unknown generator does **not** fill it in. That registration is a no-op
(the bytes match), so the declared generator is discarded — attribution is its own act, offered on
the row (ADR-0024).

## Instruments and assessors

### Authoring an instrument

Authoring is **file-based** (`../docs/seed/instruments/*.yaml`, one file per version, named
`{instrument_id}-{version}.yaml`); there is no authoring UI. Publishing is always a human act, and
a published version never changes — any change is a new version.
[`../docs/RUNBOOK-authoring-an-instrument.md`](../docs/RUNBOOK-authoring-an-instrument.md) is what
to write, which of `import-instrument` / `publish-instrument` / `bump-instrument` you want, and
when a new instrument is warranted at all.

Versions are cheap by design: iterate by bumping and deprecate freely — what reproducibility hangs
on is the version a study **pins**, never how many versions came before it. Which version a local
workbench is set up with is recorded in `../docs/seed/workbench.yaml` (ADR-0045).

### Extraction: reading a package

`content_profiling` derives a cited profile from a package's artifacts — no inference, absence is
a result (ADR-0009). One adapter per package format (`LearnpackV1`, `LearnpackV2`), each declaring
which data requirements it can supply. Teaching the system a new one is
[`../docs/RUNBOOK-adding-a-format.md`](../docs/RUNBOOK-adding-a-format.md).

Automatic profiling on registration is armed by the human acceptance of the adapter version:

```bash
uv run python -m app.cli accept-extraction --package-format LearnpackV2 --email <admin>
```

That act (ADR-0012) belongs after reviewing samples — in `/admin/profiles`, or by reading a package
by hand with `profile-content --content-id <id>`. `seed-workbench` performs it for the formats the
workbench manifest names, which is the same act replayed rather than a different one.

### Ratifying an assessor (ADR-0019)

An instrument admits 0..N assessors (ADR-0016). The registry holds `structural` for
`learnpack-course-qa` and, for `course-drafts-qa`, both `drafts-structural` (pure code) and
`drafts-hybrid` (its superset, with LLM-carried criteria). Judging for real requires a **published**
instrument version and a **ratified** assessor:

```bash
uv run python -m app.cli ratify-assessor --name drafts-hybrid --version <v> \
                                         --instrument-version-id <id> --email <admin>
```

The initial registration is the first ratification. Against a later version of the same lineage the
diff is computed mechanically, and only changed or new **executed** criteria demand
`--confirm <criterion-id>`. The same act is on `/admin/assessors` (ADR-0036), with a second step
listing each changed criterion and the `pass_condition` being confirmed; both gates run one use
case, so they cannot answer differently.

`/admin/assessors` is where that state is read: assessors grouped by kind, and per automated package
its coverage plus every version of its lineage with whether it may judge with it, who ratified it and
when. The automated rows come from `GET /admin/assessor-packages` — the in-code registry as data —
rather than from the `assessors` table, on purpose: a package nobody has ratified has no row there
at all, and it is the one worth acting on. The act itself is
`POST /admin/assessor-packages/{name}/{version}/ratify` (409 with the criteria to decide, 422 with
its cause named for everything else).

### Assessors that carry an LLM (ADR-0034)

`drafts-hybrid` extracts and classifies with an LLM and decides pass/fail in code. It needs an
**OpenRouter** `LLM_API_KEY` in the environment.

**The key is *access*. Identity is what decides the answer**, and it is pinned in the assessor's code
and declared in its `SOURCE_CONFIG`, prompts fingerprint included: which model judges, how it is
sampled (temperature, output budget, whether it may reason, how many samples decide a verdict) and
which prompts it is asked. Changing any of them without a VERSION bump is refused at ratification.
Sampling counts because it decides the answer — the second version of `drafts-hybrid` exists
because the first asked a reasoning model for an answer inside a budget its thinking consumed
whole, and got nothing back. The lineage is well past that (`/admin/assessors` says where), which
is the point: a bump is cheap and a silent change of mind is not allowed. The same goes for the upstream: the
models are pinned as OpenRouter slugs (`deepseek/…`, and the namespace *is* the provider) and every
request carries OpenRouter's own `provider` routing, which is how a misbehaving one is excluded
(ADR-0038) — so judging through another is a new assessor version, not a new `LLM_BASE_URL`.

Every `evaluate` — dry run included — spends real calls (tasks are memoized per profile, and
tokens/latency/`clean_retries` come back as `llm_*` metrics with the outcomes). When a task
irrecoverably fails — transport down, output contract never satisfied, a degeneration that survived
its one clean-conversation retry — the criteria it feeds degrade to **`execution_error`**, a fact of
the run and never of the content, carrying its cause `{task, kind, message}`, and the rest of the
evaluation persists (ADR-0037). Past the **failure budget** (a quarter of the criteria mapped for
execution) the run was not an evaluation: it aborts whole and persists nothing; fix, or just retry.
`LLM_TIMEOUT_SECONDS` bounds one call before the transport treats it as transient and backs off —
access like the key, so raising it for a slow provider re-versions nothing. The test suite never
touches the network: the transport is faked at the `runtime.get_client` seam.

## Evaluating

**The everyday path is the last one here**: a generation lands in a folder and
[`measure`](#measuring-a-generation-the-generator-just-wrote) — or `/admin/measure` — takes it
from folder to score in one act. The rest is what that chains together, and what to reach for
when a step needs doing on its own.

### One content

Calibrate an instrument — **drafts included** — against real content, spending calls but persisting
nothing:

```bash
uv run python -m app.cli evaluate --content-id <id> --instrument-version-id <id> \
                                  --assessor <name>:<version> --dry-run
```

It prints the outcome table per criterion and the claim summary. `--assessor` is always explicit:
naming which one is judging is part of the act, and `/admin/assessors` lists the versions the
registry currently carries. Without `--dry-run` it requires a published version and a ratified
assessor, then persists the evaluation (outcomes + raw metrics) and the judgment policy derives
claims, coverage and findings.

**Judgments do not combine across assessors.** The report and the fitness read the most recent
judgment per content, so within one study evaluate each content with ONE assessor.

`/admin/calibration` is the guided way to run the same loop, on the dry run's three endpoints:
`POST /admin/evaluations/preview` **starts** a run and returns its id (202),
`GET /admin/evaluations/preview/{run_id}` reads it while it advances, and `…/trace` returns every
LLM attempt whole, prompts and raw answers included. Same `PreviewEvaluation` use case the CLI
wires; started rather than awaited because with LLM-carried criteria it takes minutes. Runs live
**in memory**, last few only — the correct trade for a dry run that persists nothing. The CLI stays
the scriptable path.

### Evaluating a study in batch

A generation of the optimization experiment is a whole study's worth of courses, which is one
command (ADR-0040):

```bash
uv run python -m app.cli evaluate-study --study-id <id> [--assessor <name>:<version>] \
                                        [--concurrency N] [--re-evaluate]
```

**The study decides the assessor** (ADR-0042): it pinned one before it opened, and the run uses it.
`--assessor` is optional and is *checked* rather than obeyed — passing one that disagrees with the
pin is refused, so a script written before the pin keeps working and a mismatch is stated instead
of silently resolved.

**Progress goes to stderr, the summary to stdout** — one JSON document naming every course with its
`briefId`, its status, its duration and what it spent:

| status | what happened |
|---|---|
| `evaluated` | the course was judged and its evaluation persisted |
| `skipped` | this assessor had already evaluated it under this instrument version |
| `failed` | this course could not be judged; `cause` says why, and the others carried on |
| `cancelled` | the run stopped before reaching it; nothing was written for it |

**It refuses before it spends.** A study that is not open, no instrument or assessor pinned, an empty
dataset, an assessor that is unregistered or has not ratified the pinned version, a `--assessor` that
disagrees with the pin: each would fail identically for every course, so the command ends with the
cause named and nothing paid for. The same reasoning applies while it runs — a configuration failure,
a coverage bug or any failure this loop cannot place ends the batch on the first course, and three
consecutive transport deaths end it too (any course that completes clears that streak). A run that
ends this way reports `failed` and names the course that met it; `cancelled` is reserved for a human
stopping it, because only one of the two is a reason to go looking for a cause.

**Re-running resumes it.** What this assessor already evaluated is skipped, so a batch interrupted
at course twelve of twenty is continued by running the same command again; `--re-evaluate` asks for
all of them regardless. **Ctrl-C stops it**, and stopping means *stop starting*: courses that
finished stay persisted, the ones in flight stop at their next call, and the summary still prints.
Nothing needs undoing — an evaluation that does not reach its end writes nothing. How many courses
and how many requests run at once, and what bounds each, is [`TUNING.md`](TUNING.md).

**The same batch from the console.** `/admin/studies/<id>` carries an *Evaluation* card with the
identical work behind it — one use case, two doors. It opens on the **durable** count ("12 of 20
courses judged"), a query over the judgments rather than a run's memory: still right after a
restart, and it counts a batch someone ran from a terminal. It only offers assessors that have
**ratified the pinned version**, and while it runs it reads the run once a second, showing a row per
course. A run is refused with **409** while another one over the same courses is alive: two batches
over one course would decide by arrival order, since every reader takes the most recent judgment.
What it cannot do, on purpose: watch or cancel a batch started from the CLI — different processes,
and runs live in memory. Runs are forgotten on restart; what they wrote is not.

### Measuring a generation the generator just wrote

When the courses are a folder rather than a study, `measure` chains the whole loop — register, open
a round over exactly those courses, evaluate it, print the score:

```bash
uv run python -m app.cli measure --root generated --path learnpack-generator-04a7dd5-dirty \
                                 [--format LearnpackV2] [--assessor <name>[:<version>]] \
                                 [--instrument-version-id <id>] [--name "…"] \
                                 [--concurrency N] [--re-evaluate]
```

**Using it is `../docs/RUNBOOK-measuring.md`.** What belongs here is why it is put together this
way. Nothing new happens in it: it is the six commands a person ran by hand, with the four ids that
were copied between them derived instead. The rest is what the derivation refuses to guess:

- **The folder's name declares the generator version**, and that version — one, not "all of them" —
  is the round's scope (ADR-0044). That is the defect the chaining removes, not the typing: a round
  that measures a dataset nobody meant to name. A folder declaring `unknown` is refused likewise.
- **The norm and the judge are derived only when the derivation has one answer**: the instrument is
  the published version bound to the format, the judge is the assessor that has ratified it, and two
  of either means the command asks. `--assessor` takes `name` or `name:version`, so a daily loop
  need not be edited on every bump. Both are resolved **before** the folder is registered, since
  registering is a fetch per lesson per course.
- **Re-running resumes** rather than declaring a second round: an open study with the same name,
  norm, judge and dataset is continued, and anything less than an identical match is a new one.
- **A course keeps the generator version it was first registered with** (ADR-0035 §9), so a store
  that already holds these courses under another version measures them *there* — and `measure`
  names each one instead of composing an empty dataset.
- **One JSON document comes out**, `{"batch": …, "fitness": …}`: reading the run and the score
  separately is where a value gets paired with the wrong round.

The console does the same thing on `/admin/measure`; this is the scriptable path.

### When a criterion is not measuring what you meant

The tools are the LLM trace, repeats of one course, and two calibration dumps that build the raw
material a criterion would consume and hand it back as a table to mark up. None of them writes a
judgment: they sit outside the assessor's identity (ADR-0034) and their output is a proposal to
change the instrument, not a verdict about a course. That is a job of its own, with its own guide:
[`../docs/RUNBOOK-calibrating.md`](../docs/RUNBOOK-calibrating.md) — including how to read a trace
and what repeated runs tell you.

## Tests and CI

`uv run pytest` runs the suite; `.github/workflows/ci.yml` runs lint + format + types + the backend
suite (with Postgres as a service container) + the frontend typecheck on every PR and push to main.

**Why tests run against local Postgres.** The suite is **latency-bound**, not CPU-bound: a query to
Neon costs ~150 ms from Latam and an integration test makes over a hundred, which is a +10 min
suite; against local Postgres the same query costs ~0.3 ms. With `TEST_DATABASE_URL` set,
`tests/conftest.py` redirects the suite there and **migrates and seeds it by itself**. Without it,
tests run against `DATABASE_URL` — valid, just slow; in that case conftest does **not** migrate or
seed anything, so the real store is never touched automatically. Neon remains the store of truth:
migrations, deploy and the final smoke check.

## Modules

identity · evaluand_registry · evaluation_design · content_profiling · evaluation ·
evaluation_studies · orchestration · golden_dataset · reporting. Each with `domain/`,
`application/` and `infrastructure/`; the ones another module reads from also expose their
contract in `public.py` (`reporting` and `evaluation_studies` do not — nothing reads from them).

The plans that originated them are frozen in `../docs/design/08-code.md` (slice 1) and
`../docs/design/13-code-qa.md` (slice 2); progress lives in `../STATUS.md`.
