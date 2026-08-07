> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — design that produced slice 1 (human MVP). The current
> design is the series **`09-align-discover-qa.md` … `12-define-qa.md`** (internal QA). **Do not
> use this doc as a source for new code.**

# 05 — Connect (Context Map)

> Step 5 of the DDD Starter Modelling Process. State: **closed (v0, living)**.
> Goal: define the relation between bounded contexts / modules and what travels via
> domain events (async) vs. read queries (sync). In the modular monolith, each
> subdomain = a module with its own logical event bus.

## Relations and mechanism

| Upstream → Downstream | Pattern | Mechanism |
|---|---|---|
| Rubric Authoring → Pedagogical Evaluation | Customer/Supplier + Published Language | `RubricPublished` (event) + `getRubric(version)` (query). Evaluation stores only `rubricVersion`. |
| Content Registry → Evaluation / Orchestration | Customer/Supplier (Conformist) | lifecycle events + `getContentMetadata(id)` (query). |
| Orchestration ↔ Pedagogical Evaluation | Partnership (bidirectional, events-first) | Orchestration publishes assignments (own lifecycle) and **detects completion** (`ContentEvaluationCompleted`) by submissions threshold; Evaluation publishes `EvaluationSubmitted`; Orchestration reacts (marks the assignment `Submitted`). No cross-commands. |
| Pedagogical Evaluation → Golden Dataset | Customer/Supplier (subscriber) | subscribes to human `EvaluationSubmitted`/`ContentEvaluationCompleted`; publishes `GoldenReferenceEstablished`. |
| Orchestration → Golden Dataset | Customer/Supplier (subscriber) | Golden subscribes to `ContentEvaluationCompleted`; applies **coverage** (`coverage ≥ threshold`); publishes `GoldenReferenceEstablished`. |
| Golden Dataset + Evaluation(auto) → Calibration | Customer/Supplier (subscriber) | events + reading of both result sets → `SourceCalibrated`. `[future]` |
| Calibration → Pedagogical Evaluation | Customer/Supplier (provenance) | `SourceCalibrated` (event) + `getCalibrationStatus(assessor, rubricVersion)`. `[future]` |
| (all) → Reporting | Conformist (projections) | subscribe to events → read models. |
| Identity → (all) | Open Host Service (generic) | identity query; references `assessorId`. |

## Integration rules

1. **Default async via domain events** for reactions / state evolution between modules.
2. **Read-only sync query** for "I need the data now" (never write across modules).
3. **No cross-commands**: a module reacts to events, it does not order another one around. (The
   initial command enters from the application/UI layer into the owning module.)
4. **Published Language per upstream** = event schemas + query DTOs = the inter-module
   contract. Nobody crosses that boundary any other way.
5. This is what enables the **modulith → microservices** evolution without rewriting contracts.

## Anti-corruption layers (in the hexagon's adapters)

- **LearnPack (`GeneratingSystem`)** at the edge of Content Registry → translates its model to
  `EducationalContent`/`ContentMetadata`.
- **LLM providers (LiteLLM/OpenRouter)** in the `LLMJudge` adapter of Evaluation → translates the
  provider's response to `EvaluationResult`. `[future]`

## Outgoing integration events

`QualityJudgmentPublished` (and perhaps `ContentEvaluationCompleted`) are candidates to be published
outward (LearnPack, external reporting) via an **outbox/relay** that turns the internal
event into an API call. The "domain events → external services" pattern.

## Bridge to the MVP on Sheets

In the MVP, **"publishing an event" = appending a row** (e.g. sheet `EvaluationSubmitted`).
Events are *logical*, not mandatory infrastructure. When swapping Sheets for a real store +
bus, **the contracts between modules do not change** — only their realization. MVP edges:
Content Registry → (Orchestration, Evaluation) → Golden Dataset + Reporting + Identity, all
realizable as row appends.

## Next step

**07 — Define** (Bounded Context Canvas + Aggregate Design Canvas per context, starting with
the core `Pedagogical Evaluation`). *06 — Organise* is documented as a placeholder (small
team: a single team/owner for all modules).
