> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — design that produced slice 1 (human MVP). The current
> design is the series **`09-align-discover-qa.md` … `12-define-qa.md`** (internal QA). **Do not
> use this doc as a source for new code.**

# 02 — Discover (Big-Picture EventStorming)

> Step 2 of the DDD Starter Modelling Process. State: **closed (v0, living)**.
> Technique: Big-Picture EventStorming. Scope: **full domain** (4 sources +
> calibration). The MVP is the *prefix of the human backbone* (phases 1→4 → bridge 6).

## Legend (EventStorming convention)

- ● **domain event** (orange) — past fact, in English.
- ▸ **command / actor** (blue / yellow) — what triggers the event and who.
- ⟳ **policy** (lilac) — "when X happened → react with Y". Events-first engine.
- ⚡ **hotspot** (red) — uncertainty/decision pending for Define.
- `[MVP]` / `[future]` — membership in the slice.

## Structure: backbone + side-stream

**Evaluation** (recurring backbone, source-agnostic, with or without calibration) — subject: the
*content*. **Calibration** (occasional side-stream) — subject: the *source*. Calibration
is NOT a milestone every evaluation passes through; it branches off. Evaluating without calibrating is valid
(the source only produces judgments with more grounding if it is calibrated) → it is modelled as
*provenance* (`sourceCalibrationStatus`), not as a prerequisite.

---

## Evaluation backbone

### Phase 1 — Content inventory · opens `ContentRegistered` `[MVP]`
- ▸ Admin: `RegisterContent`, `UpdateContentMetadata`
- ● `ContentRegistered` (generatingSystem, externalId, consumableUrl, internalId)
- ● `ContentMetadataUpdated` (learningObjectives, targetAudience, prerequisites)
- ⚡ minimum mandatory vs. optional metadata?
- ⚡ versioning of the same content? (future)
- ⚡ iframe of the consumableUrl — `X-Frame-Options`/CSP (technical → Code)

### Phase 2 — Instrument ready · opens `RubricPublished` `[MVP]`
- ▸ Admin/designer: `DefineCriterion`, `AssembleRubric`, `PublishRubric`
- ● `CriterionDefined` (text, guidance, scale 1–5, anchors, grounded_in[], eligible_sources[])
- ● `RubricAssembled` (ordered criteria, draft)
- ● `RubricPublished` (*locked* version → usable) — **pivotal**
- ● `RubricDeprecated` / `RubricRevised` → new version (future)
- ⚡ **criteria immutable after publishing?** (versioning invariant — join key of calibration)
- ⚡ frameworks/dimensions/qualities as reference data from the start, or seed in MVP?
- ⚡ eligible_sources: declared already, or does MVP assume everything → `HumanExpert`?

### Phase 3 — Evaluation in progress · opens `EvaluationRunStarted` — **two realizations**
- ● `EvaluationRunStarted` (rubricVersion, contentSet, mode) — **pivotal**

**Human realization** `[MVP]` — **open and incremental** provisioning (see ADR-0002):
- ▸ Admin: `OpenCampaign` (→ `CampaignOpened`, human realization of `EvaluationRunStarted`),
  `AssignContent`, `CancelAssignment` / `ReassignAssignment`
- ● `CampaignOpened` · `AssignmentCreated` (creates `Assignment`) · `AssignmentCancelled`
- ▸ Evaluator (SME): `OpenAssignment`, `AccessContent`, `SubmitEvaluation`
- ● `AssignmentOpened`
- ● `ContentAccessed` (opened the url / consumed the content)
- ● `EvaluationSubmitted` (evaluator, content, CriterionScores[] + comments) — *workhorse,
  high frequency, NOT pivotal*

**Automatic realization** `[future]` (does not go through assignments):
- ▸ System: `RunSourceEvaluation` (batch)
- ● `MetricComputed` (raw `ComputedMetric` — for `DeterministicVerifier`/`HybridVerifier`)
- ● `EvaluationSubmitted` (automatic source; for deterministic, score via `ScoringPolicy`)

- ⟳ *`EvaluationSubmitted` → count distinct assessors of the content; on reaching the threshold
  `requiredEvaluationsPerContent` → `ContentEvaluationCompleted` (quorum by submissions, ADR-0002)*
- ⚡ **how many human evaluations per content?** (1 vs. N for inter-rater agreement —
  impacts golden quality)
- ⚡ editable draft before `SubmitEvaluation`? (draft vs. submitted)
- ⚡ simple evaluator identity tied to `EvaluationSubmitted` (no robust auth, MVP)
- ⚡ does a run mix sources per-criterion? (some criteria deterministic, others LLM)
- ⚡ costs/rate-limits of `LLMJudge` (LiteLLM/OpenRouter) → Code

### Phase 4 — Aggregation · opens `ContentEvaluationCompleted` `[MVP]`
- ● `ContentEvaluationCompleted` (content, run — **relative to the run**, not global) — **pivotal**
- ⟳ *on completion → aggregate results*
- ● `EvaluationResultsAggregated` (per-criterion aggregation via `ScoringPolicy`)
- ⚡ **how are multiple humans aggregated?** (mean/median/discard outliers/agreement threshold)
- ⚡ is "complete" = N evaluations or is 1 enough? (ties to phase 3 hotspot)

### Phase 5 — Quality judgment · opens `QualityJudgmentPublished` `[partial MVP: admin views]`
- ⟳ *aggregated results → publish judgment*
- ● `QualityJudgmentPublished` (content, rubricVersion, aggregatedScores, **provenance**:
  source + sourceCalibrationStatus)
- ⚡ rollup per set/overall in addition to per content? (admin averages — MVP views)
- ⚡ representation of the provenance (calibrated/not + against which reference)

---

## Calibration side-stream (branches off, does not continue the line)

### Bridge · `GoldenReferenceEstablished` `[MVP = final goal]`
- ● `GoldenReferenceEstablished` (a `set × rubricVersion` of human results reached
  usable ground-truth state) — **pivotal**
- ⚡ **what makes the golden "usable"?** (coverage X% with ≥N evaluations, agreement threshold)

### Calibration · `SourceCalibrated` `[future]`
- ▸ System: `RunCalibration` (requires `GoldenReference` + automatic results on *the
  same* set×rubric — which are an `EvaluationRunStarted` mode=automated pointing at the golden set)
- ● `AutomatedResultsCollectedForCalibration`
- ● `SourceCalibrated` (`CalibrationProfile` per `(Assessor, Criterion)`: agreement vs. reference)
- ⟳ *source calibrated → future `QualityJudgment`s from that source carry an updated
  assessorCalibrationStatus*
- ⚡ agreement metric per criterion (correlation / Cohen's kappa / MAE) → Define/Code
- ⚡ recalibrate on rubricVersion or model change? (calibration invalidation)

---

## Consolidated policies (state-evolution engine)

1. `EvaluationSubmitted` → *check completion* → `ContentEvaluationCompleted`?
2. `ContentEvaluationCompleted` → *aggregate* → `EvaluationResultsAggregated`
3. `EvaluationResultsAggregated` → *publish* → `QualityJudgmentPublished`
4. `GoldenReferenceEstablished` (+ automatic results) → *enables* `RunCalibration`
5. `SourceCalibrated` → *updates provenance* of future `QualityJudgmentPublished`

> These policies are internal today; several are candidates for outgoing **integration events**
> tomorrow (e.g. `QualityJudgmentPublished` → API call to LearnPack or to reporting). The
> "domain events → external services" pattern of the target modulith.

## Candidate boundaries (input for 03 — Decompose)

- **Content Registry** — phase 1.
- **Rubric Authoring** — phase 2.
- **Evaluation** (core) — phases 3–5, the recurring source-agnostic act.
- **Evaluation Orchestration** (supporting) — campaigns/assignments; wraps the human
  realization of phase 3.
- **Calibration** (supporting) — side-stream.
- **Golden Dataset** — aggregate with a life of its own (not a view over completed content).

## MVP boundary

MVP = human backbone phases **1 → 4** flowing into `GoldenReferenceEstablished` (bridge).
No `LLMJudge`, no `SourceCalibrated`. `QualityJudgmentPublished` appears partially as
the admin views (scores per course, averages).

## Hotspots resolved at the close of Discover

- ⚡→✔ **Criteria immutable after publishing.** `RubricPublished` locks the version; any
  edit ⇒ new `rubricVersion`. Rubric Authoring invariant.
- ⚡→✔ **Human quorum N=2–3 per content.** `ContentEvaluationCompleted` requires ≥N
  evaluations; `EvaluationResultsAggregated` carries mean + inter-rater agreement.
- ⚡→✔ **Usable golden = minimum coverage.** `GoldenDataset` is an aggregate with rule
  `coverage ≥ threshold` (agreement threshold optional in the future).
- ⚡→✔ **Recalibrate on model change** (see Assessor refinement): resolved by
  identity — another config = another `Assessor` = the calibration does not transfer.

## Refinement: identity of the source (`Assessor`)

The *type* is separated from the *concrete instance* that produces results:

- `EvaluationSource` = abstract type/port (HumanExpert / LLMJudge / DeterministicVerifier /
  HybridVerifier).
- **`Assessor`** = concrete, identifiable and versioned instance. It is the **provenance
  and calibration key**. For `LLMJudge` = a `SourceConfiguration`
  (model, version, sampling, promptTemplate, rubricRendering); for `HumanExpert` = the concrete
  SME; for `DeterministicVerifier` = formula/lib + thresholds.

Derived event refinements:
- `EvaluationRunStarted` and `EvaluationSubmitted` reference the `Assessor` (not just the mode).
- `SourceCalibrated` is keyed by `(Assessor, Criterion)`.
- `QualityJudgmentPublished.provenance` includes `assessor` + `assessorCalibrationStatus`.

MVP: the evaluator user IS an `Assessor` of type `HumanExpert` — the concept is instantiated
in its trivial case; the provenance slot stays open for a future `LLMJudge`. Details of
`SourceConfiguration`, reproducibility and sampling → Define/Code.

## State and next step

- Discover: **closed**.
- Next: **03 — Decompose** — group these events into subdomains (candidate boundaries
  above) and prepare Strategize (core/supporting/generic).
