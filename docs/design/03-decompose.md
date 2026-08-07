> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — design that produced slice 1 (human MVP). The current
> design is the series **`09-align-discover-qa.md` … `12-define-qa.md`** (internal QA). **Do not
> use this doc as a source for new code.**

# 03 — Decompose

> Step 3 of the DDD Starter Modelling Process. State: **closed (v0, living)**.
> Goal: group Discover's domain events into subdomains with low coupling and
> high cohesion. In the modular monolith, each subdomain ≈ one module.

## Subdomains and the events each one owns

### Pedagogical Evaluation
Produce quality judgments with provenance from `(Content, Rubric, Assessor)`.
- Events: `EvaluationRunStarted` (automatic part), `MetricComputed`, `EvaluationSubmitted`,
  `ContentEvaluationCompleted`, `EvaluationResultsAggregated`, `QualityJudgmentPublished`.
- Concepts: `Evaluation`, `EvaluationSource`/`Assessor`, `ComputedMetric`, `ScoringPolicy`,
  `CriterionScore`, `EvaluationResult`.
- Depends on: Rubric Authoring (published rubrics), Content Registry (targets + metadata).

### Rubric Authoring
The encoded pedagogical model + instrument versioning.
- Events: `CriterionDefined`, `RubricAssembled`, `RubricPublished`, `RubricRevised`,
  `RubricDeprecated`.
- Concepts: `PedagogicalFramework`, `PedagogicalDimension`, `Quality`, `EvaluationCriterion`
  (grounding N:M, `eligible_sources`, anchors), `Rubric` (versioned, immutable on publish).
- Reference data: frameworks/dimensions/qualities (versioned, not hardcoded).

### Evaluation Orchestration  *(supporting)*
Human evaluation workflow (open and incremental — see ADR-0002).
- Events: `CampaignOpened`, `AssignmentCreated`, `AssignmentOpened`, `AssignmentCancelled`,
  `ContentEvaluationCompleted`, `CampaignClosed`.
- Concepts: `EvaluationCampaign` (open; not the transactional owner of assignments), `Assignment`
  (own lifecycle), quorum by submissions threshold.
- Triggers human runs of Pedagogical Evaluation and detects completion.

### Golden Dataset  *(supporting)*
Curate the human ground truth.
- Events: `GoldenReferenceEstablished`.
- Rules: every included content reached its quorum (`ContentEvaluationCompleted`, from
  Orchestration); `coverage ≥ threshold` for "usable".
- Fed by human results from Pedagogical Evaluation.

### Calibration  *(supporting)*
Measure/adjust automatic `Assessor`s vs. the reference.
- Events: `AutomatedResultsCollectedForCalibration`, `SourceCalibrated`.
- Concepts: `CalibrationProfile` keyed by `(Assessor, Criterion)`.
- Depends on: Golden Dataset + automatic results from Pedagogical Evaluation. `[future]`

### Content Registry  *(supporting → generic)*
Register content + metadata + generator provenance.
- Events: `ContentRegistered`, `ContentMetadataUpdated`.
- Concepts: `EducationalContent`/`Course`, `GeneratingSystem`, `ContentMetadata`.

### Reporting / Projections  *(supporting-generic)*
Read models over domain events.
- Views: pending items per evaluator, scores per course, averages (per course, per evaluator,
  global). `[partial MVP]`

### Generic
- **Identity & Access** — users/evaluators/admin, auth. `[MVP: simple id]`
- **Notifications** — assignment notices, etc. `[future]`
- **Localization** — i18n EN/ES. `[future]`

## Dependency map (preview of Connect)

```
Identity  ← (all)
Content Registry ──► Pedagogical Evaluation ◄── Rubric Authoring
Evaluation Orchestration ──triggers──► Pedagogical Evaluation (human runs)
Pedagogical Evaluation ──human results──► Golden Dataset
Golden Dataset + automatic results ──► Calibration
Pedagogical Evaluation / Orchestration ──events──► Reporting
```

These arrows are the allowed event/API flows between modules of the monolith.

## Next step
**04 — Strategize** (core/supporting/generic classification + Core Domain Chart).
