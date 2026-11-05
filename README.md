# LearnPack Evals

LearnPack generates courses with AI, and the team keeps changing the generator that writes them.
This repository answers the question each change raises — **does the new generator version
produce courses that teach better or worse, and in what exactly?** — and shows the evidence
behind every answer.

It works in two halves, and the second is what makes the first trustworthy:

- **Automated measurement.** Software reads the files a generator produced for each course and
  checks them against written pedagogical criteria: one verdict per criterion, each resting on
  a passage of the course. Run over many courses, it shows what a generator version does well
  and badly.
- **Expert reference.** Subject-matter experts rate the same courses, one quality at a time, on
  a 1–5 scale. Their ratings are what the automated side is checked against: for each thing it
  claims about a course, how often it agrees with the experts. How much the experts agree with
  one another is the most any automated check can be expected to reach.

## How it flows

```
generator version ─▶ package ─▶ profile ─▶ assessor ─▶ an outcome per criterion ─▶ study report
                                               ▲
                                          instrument
                                     (claims and criteria)

experts ─▶ campaign ─▶ a 1–5 rating per quality ─▶ does each claim follow the experts?
```

## The words you will meet

Each term below is the name the code and the rest of the documentation use, and
`docs/GLOSSARY.md` defines it in full. If you come from other evals tooling, the glossary's
"Equivalences with the evals industry" maps that vocabulary onto this one.

| Term | In plain words |
|---|---|
| **generator version** | one version of the course generator being measured |
| **package** | everything a generator delivers for one course. Its **format** says how to read it: `LearnpackV1` is a finished course, `LearnpackV2` a draft |
| **profile** | what a package says, extracted **verbatim** with the location of each piece — never inferred, never summarized |
| **quality** | one pedagogical property a course can have, such as how its cognitive demand progresses. Qualities are grouped into **dimensions** |
| **instrument** | a versioned, published set of **claims** — one-sentence assertions, each about one quality — and of the **criteria** that evidence them |
| **criterion** | one verifiable condition with a written **pass condition**, e.g. "no lesson's vocabulary runs far above the rest of the course" |
| **assessor** | versioned software that decides an instrument's criteria. A different algorithm, prompt or model is a different assessor |
| **study** | one measurement round: the generator versions to compare, the courses each wrote from the same commissions, and the instrument version that measures them, ending in a frozen report |
| **campaign** | one round of expert rating, with its own courses and its own result |
| **reference instrument** | what the experts answer: one 1–5 statement per quality. It is not the automated instrument; the two share only the qualities |

## An example, end to end

The criterion `cr-no-lesson-spikes-in-lexical-load` evidences the claim *"No single lesson's text
runs far ahead of the course's own level"*, about how a course's cognitive demand progresses. Its
pass condition: no lesson's mean syllables per word may exceed the course's own median by more
than 0.20.

Over `object-representation-in-python`, one of the five real courses its threshold was set
against, the assessor measures 11 lessons and finds a median of 1.656, with two lessons above
the margin — the highest is `02.1-dot-notation`, at +0.243. The outcome is **`fail`**, carrying
the failure mode the instrument declares (*"One lesson is written for a markedly more advanced
reader than the rest of the course"*), the lesson text it measured as evidence, and the numbers
behind it. `backend/tests/test_calibration.py` pins that result, and `docs/MEASUREMENT.md` says
why the measure and its threshold are what they are.

Code alone decided that one. Others need a model to read the course — see below.

## Two rules that hold everywhere

- **There is no total score.** A course is never reduced to one number: results are read
  criterion by criterion. Where a number is computed — the share of criteria that pass — it
  covers one declared set, a quality or a dimension, and travels with its coverage: how many
  criteria counted and how many could not be decided.
- **A verdict cites its evidence** — a passage and its location in the package, or an explicit
  record that there was none. "The model said so" is not a result.

## How a criterion is decided

An instrument's criteria say *what* is verified; the assessor that executes them decides *how*,
criterion by criterion. There are three ways, and an assessor may also decline:

| | What a model does | What code does |
|---|---|---|
| **deterministic** | nothing | counts, checks presence and order, computes measures such as lexical load |
| **model extracts, code decides** | reads the course and returns grounded data: the outcomes it states, the level of each objective, which task measures which objective, where each concept appears | applies the pass condition to that data — a count, an order, a trajectory |
| **model judges** | answers the pass condition itself, citing a passage | checks the citation, asks again, takes the majority |
| **abstains** | — | nothing: the criterion ends `not_assessed`. Nobody decides it, and it shows as a gap in coverage, not as a fail |

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

`task setup` leaves a database ready to measure: the instruments are published, the package
formats it reads are enabled, each assessor is approved against the instrument it judges, and
the generator is registered — `docs/seed/workbench.yaml` says exactly which. Sign in at http://localhost:3000 as
`admin@local.dev`; the setup records everything it does as that user.

The expert side needs people to rate and courses to rate, which measuring does not:
`task seed:demo` adds two evaluators, two courses and an open campaign. `task db:reset` starts
over from an empty database.

## Where to go

| You want to… | Read |
|---|---|
| measure what a generator produced | `docs/RUNBOOK-measuring.md` — self-contained, start here |
| find out why a criterion answered that | `docs/RUNBOOK-calibrating.md` |
| write or revise an instrument | `docs/RUNBOOK-authoring-an-instrument.md` |
| teach the system a new package format | `docs/RUNBOOK-adding-a-format.md` |
| know how each criterion is decided — code, a model's data, or a model's verdict | `docs/MEASUREMENT.md` |
| look up a term | `docs/GLOSSARY.md` |
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
docs/       Architecture, vocabulary, decisions and runbooks.
courses/    The packages under measurement, one folder per generator version. Never versioned.
```

## If you contribute: how the documentation works

The documentation is the source of truth, and each kind of document makes a different promise:

| | |
|---|---|
| `docs/ARCHITECTURE.md` | the rules that do not bend — dependency direction, module isolation |
| `docs/GLOSSARY.md` | the vocabulary; **code names come from here** |
| `docs/adr/` | the decisions, **immutable** — one is superseded by a new one, never edited |
| `docs/design/` | frozen snapshots, **not maintained** — an ADR that contradicts one wins |
| `STATUS.md` | the only dated status in the repo — short on purpose, and never a log |

Everything else — this README, `backend/README.md`, `frontend/README.md`, `docs/DATA_MODEL.md`,
`docs/MEASUREMENT.md` and the runbooks — is **reference**: true of `main`, and updated in the
same commit as the code that would make it false.
