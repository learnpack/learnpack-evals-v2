# LearnPack Evals

Measures the **pedagogical quality of AI-generated courses**, and shows its work.

Two halves, and the second is what makes the first trustworthy:

- **An automated instrument** reads the package a generator delivered, extracts the evidence
  its criteria ask for, and judges each criterion against a written pass condition. A **study**
  runs it over many courses and reports what a generator version does well and badly.
- **A panel of subject-matter experts** answers a reference instrument about those same
  courses. How much the experts agree is the ceiling the automated side can be held to, and
  their answers are the reference it is validated against.

Two rules hold everywhere, and most of the design follows from them:

- **There is no single score.** A result is a profile per criterion, each carrying its own
  denominator. Nothing is ever averaged across criteria.
- **A verdict cites its evidence** — a quote and its location in the package, or an explicit
  record that there was none. "The model said so" is not a result.

## How a criterion is decided

An instrument's criteria say *what* is verified; the assessor that executes them decides *how*,
criterion by criterion. There are three ways, and an assessor may also decline:

| | What a model does | What code does |
|---|---|---|
| **deterministic** | nothing | counts, checks presence and order, computes measures such as lexical load |
| **model extracts, code decides** | reads the course and returns grounded data: the outcomes it states, the level of each objective, which task measures which objective, where each concept appears | applies the pass condition to that data — a count, an order, a trajectory |
| **model judges** | answers the pass condition itself, citing a passage | checks the citation, asks again, takes the majority |
| **abstains** | — | nothing: the criterion is `not_assessed`, and only a human judges it |

How many criteria each assessor decides each way, and which, is in `docs/MEASUREMENT.md` — a
test fails when that table stops matching the code.

## Run it

Everything runs on your machine: Postgres in a container, no accounts to create, nothing to
deploy. You need Docker, [Task](https://taskfile.dev/installation/),
[uv](https://docs.astral.sh/uv/) and Node 20+. The one thing that leaves the machine is a model
call: measuring with an assessor that extracts or judges through a model needs an OpenRouter key
in `LLM_API_KEY` (`backend/README.md`); the deterministic ones need nothing.

```bash
task setup   # once: env files, dependencies, database, migrations, seed
task dev     # the API on :8000 and the console on :3000
```

`task setup` leaves a database that can **measure**: instruments published, extractions
accepted, assessors ratified, generator lineages registered. Sign in at
http://localhost:3000 as `admin@local.dev`, the identity the setup attributes its acts to.

The **human panel's** flow needs evaluators and something to judge, which measuring does not:
`task seed:demo` adds two of them, two courses and an open campaign. `task db:reset` starts
over from an empty database.

## Where to go

| You want to… | Read |
|---|---|
| measure what a generator produced | `docs/RUNBOOK-measuring.md` — self-contained, start here |
| find out why a criterion answered that | `docs/RUNBOOK-calibrating.md` |
| write or revise an instrument | `docs/RUNBOOK-authoring-an-instrument.md` |
| teach the system a new package format | `docs/RUNBOOK-adding-a-format.md` |
| know how each criterion is decided — code, a model's data, or a model's verdict | `docs/MEASUREMENT.md` |
| run the backend, find a command or a setting | `backend/README.md` |
| make a batch faster, or find which ceiling holds it back | `backend/TUNING.md` |
| work on the console | `frontend/README.md` |
| deploy an instance for an expert campaign | `backend/ENVIRONMENT.md` |
| know what is built and what is not | `STATUS.md` |
| find the decision behind a rule | `docs/README.md` — the index of every ADR |

## The repo

```
backend/    FastAPI + Postgres. Hexagonal, events-first.
frontend/   Next.js + Tailwind. The evaluator's flow and the admin console.
docs/       Why every boundary is where it is.
courses/    The packages under measurement, one folder per generator version. Never versioned.
```

## Reading the documentation

The documentation is the source of truth, and each kind of document makes a different promise:

| | |
|---|---|
| `docs/ARCHITECTURE.md` | the rules that do not bend — dependency direction, module isolation |
| `docs/GLOSSARY.md` | the vocabulary; **code names come from here** |
| `docs/adr/` | the decisions, **immutable** — one is superseded by a new one, never edited |
| `docs/design/` | frozen snapshots, **not maintained** — an ADR that contradicts one wins |
| `STATUS.md` | the only dated status in the repo — short on purpose, and never a log |

Everything else — the two READMEs above, `docs/DATA_MODEL.md`, `docs/MEASUREMENT.md`, the
runbooks — is **reference**: true of `main`, and updated in the same commit as the code that
would make it false.
