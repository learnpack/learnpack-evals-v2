# LearnPack Evals

A system to **evaluate the pedagogical quality of AI-generated educational content**, built in
two slices:

- **Human evaluation (MVP):** a panel of experts scores courses against a versioned rubric; the
  system aggregates the judgments (per-criterion averages, inter-rater dispersion — never a
  single aggregate score) and establishes a **golden dataset** of human reference results.
- **Generator QA engine:** instruments as versioned **evidential arguments** (claims backed by
  verifiable criteria), **content profiling** that extracts cited evidence from the package a
  generator delivers, **automated assessors** that judge criteria mechanically, and studies
  that accumulate judgments per generator.

Where development stands today: **`STATUS.md`**.

- **`docs/RUNBOOK-measuring.md`** — **measuring what a generator produced**, end to end. Start here if
  that is what you came for; it does not assume you will read anything else.
- **`docs/`** — the design and the why of every boundary. `docs/ARCHITECTURE.md` is the hard
  rules; `docs/GLOSSARY.md` names everything in the code.
- **`backend/`** — FastAPI + Postgres, hexagonal, events-first.
- **`frontend/`** — Next.js + Tailwind: the evaluator flow and the admin console.

## Run it locally, no accounts and no cloud

Local mode: database in Docker, **no authentication**, and a workbench ready to measure.
Requires Docker (Compose with `--wait`; the daemon must be running — e.g. Docker Desktop
started), [Task](https://taskfile.dev/installation/), [uv](https://docs.astral.sh/uv/) and
Node 20+.

```bash
# One-time setup, then daily dev
task setup
task dev
```

`task setup` leaves a database that can **measure**: the instruments
`docs/seed/workbench.yaml` names are published, their extraction adapters are accepted, every
automated assessor is ratified, and the generator lineages are registered (ADR-0045). To start
over from zero — this destroys the local database and rebuilds it:

```bash
task db:reset
```

`task dev` starts Postgres, the API at http://localhost:8000 and the frontend at
http://localhost:3000 (both servers share one terminal). Ctrl+C stops the API and frontend;
Postgres keeps running until `task db:down`.

To run each server in its own terminal:

```bash
task db        # terminal 1 (or once; leaves Postgres in the background)
task backend   # terminal 2 — http://localhost:8000
task frontend  # terminal 3 — http://localhost:3000
```

### Manual setup (without Task)

```bash
# 1. Database
cd backend && docker compose up -d

# 2. Backend  (http://localhost:8000)
cp .env.example .env        # ships in local mode: nothing to fill in
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed             # rubric v1 + pedagogical reference data
uv run python -m app.cli seed-workbench   # instruments published, extractions accepted,
                                          # assessors ratified, generator lineages registered
uv run uvicorn app.main:app --reload

# 3. Frontend  (http://localhost:3000)
cd frontend
cp .env.local.example .env.local     # ships with NEXT_PUBLIC_AUTH_MODE=local
npm install
npm run dev
```

Sign in at `/sign-in` as `admin@local.dev`, which is the identity the setup creates and
attributes its acts to.

### The two auth modes

The same checkout runs either way — the switch is **two variables, one per side**, and they
have to say the same thing:

| | no accounts, no cloud | the real provider |
|---|---|---|
| `backend/.env` | `AUTH_MODE=local` | `AUTH_MODE=clerk` |
| `frontend/.env.local` | `NEXT_PUBLIC_AUTH_MODE=local` | `NEXT_PUBLIC_AUTH_MODE=clerk` |

Clerk works against `localhost` too — its development instance is built for it — so the real
login and invitation flows can be exercised without deploying anything. What that needs
(keys, JWT template, what stops working) is in `backend/ENVIRONMENT.md`, *Running Clerk
against your own machine*.

Two things to know:

- **Restart after changing them.** Neither side re-reads its value while running.
- **If they disagree, every request is a 401** — and the API says so in as many words,
  naming both files. It is not an expired session.

The **human evaluation** flow needs raters, which the setup does not install — they belong to
that flow, not to measuring a generator. `task seed:demo` adds them, with two frozen courses and
an open campaign to work on:

| User | Role | For |
|---|---|---|
| `admin@local.dev` | admin | register courses/generators, instruments, profiles, campaigns, reports |
| `ada.lovelace@local.dev` | evaluator | evaluate |
| `grace.hopper@local.dev` | evaluator | evaluate (the second rater: without it there is no inter-rater) |

Switch users from the header menu. To wipe just that demo dataset and reload it:
`uv run python -m app.cli seed-demo --reset`.

### Iterating on the seeds

- `docs/seed/workbench.yaml` declares what a local workbench is built from — which instrument
  versions are published, which extractions are accepted, which generator lineages exist
  (ADR-0045). Edit it and re-run `uv run python -m app.cli seed-workbench` (idempotent).
- `docs/seed/rubric-v2.json` + `docs/seed/pedagogical-reference.yaml` are the source of truth
  for the human reference instrument and the reference data; edit and re-run
  `uv run python -m app.cli seed` (in-place, idempotent).
- `docs/seed/instruments/*.yaml` are authored instrument drafts;
  `uv run python -m app.cli import-instrument --file <yaml>` creates or replaces the draft.
  Publishing is a deliberate human act (the Publish button in `/admin/instruments`, or
  `publish-instrument`); the workbench manifest is where the team records which version a local
  store is set up with. Published versions are immutable.

## Production

Clerk (invite-only) + Neon + Render + Netlify. Local mode does **not** apply there:
`AUTH_MODE=local` with `ENVIRONMENT=production` refuses to boot. Preparing one is
`backend/ENVIRONMENT.md`; see also `frontend/README.md` and `docs/design/08-code.md` §10.
