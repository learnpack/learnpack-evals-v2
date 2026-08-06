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

- **`docs/`** — the design and the why of every boundary. `docs/ARCHITECTURE.md` is the hard
  rules; `docs/GLOSSARY.md` names everything in the code.
- **`backend/`** — FastAPI + Postgres, hexagonal, events-first.
- **`frontend/`** — Next.js + Tailwind: the evaluator flow and the admin console.

## Run it locally, no accounts and no cloud

Local mode: database in Docker, **no authentication**, demo users and data pre-loaded.
Requires Docker, [uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
# 1. Database
cd backend && docker compose up -d

# 2. Backend  (http://localhost:8000)
cp .env.example .env        # ships in local mode: nothing to fill in
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed        # rubric v1 + pedagogical reference data
uv run python -m app.cli seed-demo   # users, demo courses (profiled from real frozen
                                     # packages), instrument draft, open campaign, assignments
uv run uvicorn app.main:app --reload

# 3. Frontend  (http://localhost:3000)
cd frontend
cp .env.local.example .env.local     # ships with NEXT_PUBLIC_AUTH_MODE=local
npm install
npm run dev
```

At `/sign-in` pick who to enter as:

| User | Role | For |
|---|---|---|
| `admin@local.dev` | admin | register courses/generators, instruments, profiles, campaigns, reports |
| `ada.lovelace@local.dev` | evaluator | evaluate |
| `grace.hopper@local.dev` | evaluator | evaluate (the second rater: without it there is no inter-rater) |

Switch users from the header menu. To start over — wipes the local dataset and reseeds it:
`uv run python -m app.cli seed-demo --reset`.

### Iterating on the seeds

- `docs/seed/rubric-v1.json` + `docs/seed/pedagogical-reference.yaml` are the source of truth
  for the human rubric and the reference data; edit and re-run `uv run python -m app.cli seed`
  (in-place, idempotent).
- `docs/seed/instruments/*.yaml` are authored instrument drafts;
  `uv run python -m app.cli import-instrument --file <yaml>` creates or replaces the draft.
  Publishing is a deliberate human act (the Publish button in `/admin/instruments`, or
  `publish-instrument`) — published versions are immutable.

## Production

Clerk (invite-only) + Neon + Render + Netlify. Local mode does **not** apply there:
`AUTH_MODE=local` with `ENVIRONMENT=production` refuses to boot. See `backend/README.md`,
`frontend/README.md` and `docs/design/08-code.md` §10.
