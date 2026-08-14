# docs — index

Design of a system to **evaluate the pedagogical quality of AI-generated educational
content**, following the DDD Starter Modelling Process (ddd-crew).

## How the documentation is organized

Every document carries a **maintenance contract**, declared by its location:

| Where | Class | Contract |
|---|---|---|
| **`docs/` root** | reference | **Always true of `main`.** Changes in the same commit as the code. No dates, no status. |
| `docs/adr/` | decision | **Immutable.** An ADR is never edited: a new one supersedes it. Sole exception: the superseded ADR's **Estado** line is updated to point at its successor. |
| `docs/design/` | snapshot | **Frozen.** What we thought and why, at the time. Not maintained. |
| `../backend/README.md`, `../frontend/README.md` | reference | Operational runbook, next to the code it operates. |
| `../STATUS.md` | status | **The only place with dated status.** Rewritten whole. |
| `notes/` (gitignored) | working | Ephemeral. When the task closes: promoted or deleted. |

Rule for admitting something into the `docs/` root: *will it still be true six months from now
without anyone touching it?* If not, it does not belong there. The full rules — including what
to do with a note when its task ends — are in `../CLAUDE.md`, section **Documentation**.

## Reading order (for Claude Code)

1. `../CLAUDE.md` — non-negotiables (repo root).
2. `ARCHITECTURE.md` — Dependency Rule, hexagonal, module isolation, events-first.
3. `GLOSSARY.md` — ubiquitous language. **Code names come from here.**
4. `design/09`–`13` — **the current design** (generator QA): strategic (09–11), tactical (12)
   and the code plan (13). `design/01`–`08` are historical snapshots of slice 1.
5. `adr/` — the immutable decisions. Then `../STATUS.md` for where development stands.

## Contents

**Current (reference)**
- `ARCHITECTURE.md` — non-negotiable invariants.
- `GLOSSARY.md` — ubiquitous language.
- `DATA_MODEL.md` — logical Postgres schema (tables, ownership, FK vs app-level refs).
- `MEASUREMENT.md` — where a `ComputedMetric` is computed, what each one means, and the evidence
  behind every threshold — including the measures that were tried and rejected.

**Decisions (`adr/`, immutable)**
`0001` open content metadata *(superseded by 0017)* · `0002` campaigns/assignments/quorum ·
`0003` Postgres + events · `0004` Clerk · `0005` Evaluation identity + content versioning ·
`0006` reporting via query ports · `0007` admin bootstrap (provisioning allowlist) · `0008`
local mode (no Clerk, no Neon) · `0009` extraction without inference · `0010` criteria as
verifiable conditions · `0011` no single aggregate score · `0012` genesis of instruments ·
`0013` design with ECD-lite · `0014` vocabulary in evidence models · `0015` human reference in
two layers · `0016` uniform automated assessors · `0017` the declared surface is the package ·
`0018` declared assessor coverage + `not_assessed` · `0019` assessor coverage by criterion
lineage + per-version ratification · `0020` mandatory, checked value domains · `0021` the
absence-derived `fail`: no quote, origin recorded · `0022` mechanical brief intake · `0023` the
fitness projection · `0024` explicit generator attribution · `0025` pedagogical frames (decided,
not built) · `0026` a claim asserts about exactly one quality · `0027` package intake by
mechanical discovery · `0028` a consumable URL declares a deployment · `0029` automatic profiling
assumes http(s) transport · `0030` the generator declares reference data, not artifacts · `0031` a
generator is an entity; its versions belong to it · `0032` an instrument forks when its claims
change, not the package format · `0033` registered content is never retired · `0034`
LLM-carrying assessors: semantics are identity, transport is environment · `0035` local sources
are declared roots · `0036` ratification is offered at both gates · `0037` execution failure is
an outcome (`execution_error`, the failure budget, the three-way retry) · `0038` the upstreams
that may serve a model are assessor identity · `0039` the brief groups the fitness projection;
it is not a grain of it · `0040` a batch is a run · `0041` the frozen report is the record, not
the reading surface.

**Snapshots (`design/`, frozen)**
Steps 01–08 of the modelling process (slice 1, historical) · the 09–13 series (generator QA:
the current design and its code plan) · `research/`. See `design/README.md`.

**Assets** (not documentation)
- `seed/rubric-v1.json` + `seed/pedagogical-reference.yaml` — human rubric and reference data;
  consumed by `app.cli seed`.
- `seed/instruments/*.yaml` — authored instrument drafts; consumed by
  `app.cli import-instrument` (and by `seed-demo` in local mode).

## MVP stack (confirmed)

Next.js/Tailwind/shadcn on **Netlify** · **FastAPI** on **Render Starter** · Postgres/pgvector
on **Neon** · **Clerk** (invite-only) as identity. Details in `design/08-code.md`.

## The north star, in two sentences

- **Core = pedagogical evaluation** (producing multi-source, multi-criterion quality judgments
  with provenance, calibratable). **Calibration is NOT the core.**
- **Two horizons:** the target model is fully documented; **each increment is a thin slice**
  that must not close doors on it.
