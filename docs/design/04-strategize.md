> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — design that produced slice 1 (human MVP). The current
> design is the series **`09-align-discover-qa.md` … `12-define-qa.md`** (internal QA). **Do not
> use this doc as a source for new code.**

# 04 — Strategize (Core Domain Chart)

> Step 4 of the DDD Starter Modelling Process. State: **closed (v0, living)**.
> Chart axes: business differentiation (vertical) × model complexity (horizontal).
> Core = high differentiation + high complexity (top-right).

## Classification

| Subdomain | Class | Differentiation | Complexity | Note |
|---|---|---|---|---|
| Pedagogical Evaluation | **Core** | high | high | The product's reason for being. |
| Rubric Authoring | **Core (secondary)** | high | high | Encloses the expertise; its CRUD is thin. |
| Golden Dataset | Supporting | medium-high | medium | Ground truth; aggregate with rules. |
| Calibration | Supporting | medium (high potential) | high | Validates/serves the core; it is **not** the core. |
| Evaluation Orchestration | Supporting | low-medium | medium | Necessary human workflow. |
| Content Registry | Supporting→Generic | low | low-medium | Domain-informed metadata. |
| Reporting / Projections | Supporting-generic | low | low | Read models. |
| Identity & Access | Generic | low | low | Off-the-shelf auth. |
| Notifications | Generic | low | low | — |
| Localization | Generic | low | low | i18n. |

## Key strategic decision (recorded)

**Core = pedagogical evaluation, NOT calibration.** Calibration has differentiation
potential, but it is deliberately classified as *supporting*: it validates and serves the core.
The differentiator is the *ability to produce reliable, multi-source and multi-criterion
quality judgments*, not the process that validates them against humans.

## Investment guide

- **Rich domain model, clean architecture, carefully tended invariants:**
  `Pedagogical Evaluation` + the *model* of `Rubric Authoring`.
- **Pragmatic and thin (good-enough, no over-engineering):**
  `Orchestration`, `Golden Dataset`, `Content Registry`, `Reporting`.
- **Buy / adopt / trivial:** `Identity`, `Notifications`, `Localization`.

## Implication for the MVP

The MVP exercises **almost pure supporting/generic** (`Orchestration` + `Content Registry` +
`Golden Dataset` as the goal + admin `Reporting` + simple `Identity`) with **a trivial
slice of the core** (the human `EvaluationSubmitted` and its persistence). That is why it can
be built lightweight (even on Sheets) without compromising the core: the heavy part of the core
(automatic sources, metrics, calibration) is all `[future]`.

## Next step
**05 — Connect** (context map + relations between bounded contexts / modules, and flows of
domain events / integration events).
