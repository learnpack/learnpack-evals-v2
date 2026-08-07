> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — tactical design that produced slice 1 (human MVP).
> **Superseded by `12-define-qa.md`** (self-contained — includes the contexts of this doc with
> their adjustments). **Do not use this doc as a source for new code.** Note: the invariant
> "score ∈ [1,5], exact coverage" of Evaluation was superseded by the tri-state (ADR-0010,
> `12-define-qa.md`); `Rubric v1` survives as the reference instrument (ADR-0015).

# 07 — Define (option B: MVP slice)

> Step 7 of the DDD Starter Modelling Process. State: **in progress**.
> Scope (option B): only what the MVP touches — the human slice. Contexts:
> Rubric Authoring · Content Registry · Evaluation (human) · Evaluation Orchestration ·
> Golden Dataset · Reporting · Identity. Each one: Bounded Context Canvas + Aggregate Design
> Canvas. Decisions are made without closing doors to the target model (01–05).

Definition order: **Rubric Authoring** (the evaluator's input) → Evaluation (human) →
Content Registry → Orchestration → Golden Dataset → Reporting → Identity.

---

## Rubric Authoring

### Bounded Context Canvas
- **Purpose:** define and version the evaluation instruments (`Rubric`) and the pedagogical
  model that grounds them (frameworks → dimensions → qualities → criteria, with grounding
  and `eligible_sources`); guarantee the immutability of a published rubric.
- **Classification:** Core (secondary). Rich model; thin workflow/CRUD.
- **Inbound** — Commands: `DefineCriterion`, `AssembleRubric`, `PublishRubric`,
  `ReviseRubric`, `DeprecateRubric`. Query: `getRubric(rubricVersion) → RubricSnapshot`.
- **Outbound** — Events: `CriterionDefined`, `RubricAssembled`, `RubricPublished` (carries the
  `RubricSnapshot`), `RubricRevised`, `RubricDeprecated`.
- **Published Language `RubricSnapshot`:**
  `{ rubricId, version, criteria: [{ criterionId, prompt, guidance, scaleMin:1, scaleMax:5,
  anchorLow, anchorHigh, eligibleSources[], groundedIn[] }] }`.
- **Ubiquitous language:** PedagogicalFramework, PedagogicalDimension, Quality,
  EvaluationCriterion, Rubric, rubricVersion, anchors, eligible_sources.
- **Open questions:** explicit `Draft` state in MVP vs direct seed to `Published`; weights per
  criterion (MVP: no weights, simple mean); naming `Quality` vs `PedagogicalAttribute`.

### Aggregate Design Canvas — `Rubric`
- **Description:** ordered, immutable version of criteria for evaluating content. Root =
  `Rubric` (one version); **owns** its `Criterion`s (VOs). **References by id**
  `PedagogicalFramework`/`Quality` (reference data, outside the boundary).
- **Lifecycle:** `Draft → Published (→ Deprecated)`. MVP: direct seed to `Published`.
- **Invariants:**
  1. `Published` ⇒ immutable version; frozen criteria. Change ⇒ new `rubricVersion`.
  2. ≥1 criterion; each criterion: scale 1–5, both anchors (1 and 5), `prompt` + `guidance`
     present, `eligible_sources` ≥1.
  3. `criterionId` unique within the rubric.
  4. `rubricVersion` stable and global (join key of evaluation and calibration).
- **Enforcement:** synchronous; atomic `PublishRubric` (whole aggregate = one transactional
  boundary). No corrective policies.
- **Commands → events:** `DefineCriterion→CriterionDefined`, `AssembleRubric→RubricAssembled`,
  `PublishRubric→RubricPublished`, `ReviseRubric→RubricRevised`,
  `DeprecateRubric→RubricDeprecated`.
- **Size:** small (v1 = 5 criteria).
- **MVP realization:** no authoring UI. `Rubric v1` = *seed data* of a `Published`, locked
  version. Authoring commands `[future]`. The evaluator consumes a read-only
  `RubricSnapshot v1`.

### Reference data (small aggregates, seeded in MVP)
`PedagogicalFramework`, `PedagogicalDimension`, `Quality` — minimal CRUD; seeded in the MVP.
The criteria reference them by id (`groundedIn[]`, dimension/quality).

### Rubric v1 — instantiated (seed in `../seed/rubric-v1.json`)
5 criteria (one per dimension; each criterion collapses the qualities of its dimension into one
1–5 question). Generic anchors (1 = not at all/very low, 5 = fully/very high). Scope: pedagogical
quality of the **content** (objectives, lessons, coherence, progression); **excludes
presentation and ecosystem**.

| # | criterionId | dimension | groundedIn |
|---|---|---|---|
| 1 | `objectives-quality` | Quality and soundness of objectives | Biggs · Revised Bloom · SOLO |
| 2 | `constructive-alignment` | Constructive alignment (objective↔content) | Biggs · Revised Bloom |
| 3 | `instructional-design` | Instructional design of the lesson | Merrill |
| 4 | `inter-lesson-coherence` | Coherence and continuity between lessons | Schmidt |
| 5 | `learning-progression` | Learning progression | Learning progressions · SOLO · Merrill · Schmidt · Revised Bloom |

Observations that confirm/refine the model:
- **Criterion ↔ Dimension is 1:1 in v1** (score per dimension, collapsing qualities). The model
  already admits it (Criterion operationalizes Quality *or* Dimension).
- **Grounding at the Quality level, aggregated onto the Criterion** (`Criterion.groundedIn` = union of the
  frameworks of the qualities of its dimension). The 21 qualities + 5 dimensions + 6 frameworks
  are seedable reference data.
- **Generic anchors** (same 1/5). Open question: per-criterion anchors in the future?
- **`eligible_sources` v1 = [HumanExpert]** in all 5. Candidates for future automation
  (informative): 1–2 → Bloom-tagging/embeddings; 4 → Coh-Metrix; etc.
- **Metadata (corrected):** evaluators receive the **full course** (all lessons);
  the `lessonPlan` was from a previous version and is discarded. Content metadata is modelled
  **open/extensible** (no fixed fields) — see ADR-0001 and Content Registry.

---

## Evaluation (human part, MVP)

### Bounded Context Canvas
- **Purpose:** produce and persist the judgment of an `Assessor` on a content using a
  rubric — the core act. MVP: only `HumanExpert`.
- **Classification:** Core.
- **Inbound** — Command: `SubmitEvaluation(assessorId, contentId, rubricVersion, scores[])`.
  Queries: `getRubric(rubricVersion)`, `getContentMetadata(contentId)`.
- **Outbound** — Event: `EvaluationSubmitted(assessorId, contentId, rubricVersion,
  EvaluationResult, mode=human)`. Does not publish `ContentEvaluationCompleted` (see refinement).
- **Ubiquitous language:** Evaluation, EvaluationResult, CriterionScore, Assessor, provenance.

### Aggregate Design Canvas — `Evaluation`
- **Description:** a concrete **act** of evaluation. Root = `Evaluation` (own id
  `evaluationId`), with coordinates `{assessorId, contentId (version), rubricVersion,
  occurredAt/attempt}`; contains an `EvaluationResult` (the `CriterionScore`s + comments).
- **Lifecycle (MVP):** `Submitted`. (Draft/InProgress = `[future]`.)
- **Invariants:**
  1. Exact coverage: one `CriterionScore` for each `criterionId` of the `rubricVersion` (none
     missing, none extra).
  2. score ∈ [1,5] integer; comment optional.
  3. Valid references: published `rubricVersion`, registered `contentId` (version), `assessorId`.
  4. **Identity = own `evaluationId`. There is NO uniqueness by `(assessor, content, rubric)`:**
     **repetitions** of the same `Assessor` on the same `(content, rubric)` are allowed (necessary
     for `LLMJudge` dispersion) and evaluating different `contentVersion`s. Human anti-duplication
     is enforced in the `Assignment` (Orchestration), not here. See ADR-0005.
  5. Immutable once `Submitted` (MVP).
- **Consistency boundary:** `Evaluation` + `EvaluationResult` = transactional unit; atomic
  submit.
- **Command → event:** `SubmitEvaluation → EvaluationSubmitted`.
- **Corrective policies:** synchronous validation; invalid rubric/criteria → rejection. Submitting on
  an `Assignment` already `Submitted` → 409 (Orchestration rule).
- **Throughput/size:** low, no concurrency; small aggregate (5 scores).
- **Provenance:** `EvaluationSubmitted` carries the `Assessor` (HumanExpert id), `mode=human`.

> **Refinement vs Discover:** `ContentEvaluationCompleted` is emitted by **Orchestration** (which
> knows the quorum: it created N assignments per content and detects completion on receiving the
> `EvaluationSubmitted`s), not the core `Evaluation`. Cross-evaluator aggregation (mean +
> inter-rater) remains a Reporting/Golden projection.

### MVP realization
`SubmitEvaluation` → `INSERT` into `evaluations` + `criterion_scores` and a row in `events`
(`EvaluationSubmitted`), in one transaction (ADR-0003). Completion is handled by Orchestration
via assignment status (see 08 §5).

---

## Content Registry (supporting → generic)

### Bounded Context Canvas
- **Purpose:** register evaluable content + its metadata (open/extensible) + provenance of the
  generating system; serve metadata to consumers.
- **Inbound** — Commands: `RegisterContent`, `UpdateContentMetadata`. Queries:
  `getContentMetadata(contentId)`, `getContentSnapshot(contentId)`. ACL: LearnPack ingestion
  (MVP: manual load → trivial ACL).
- **Outbound** — Events: `ContentRegistered`, `ContentMetadataUpdated`. DTO:
  `ContentSnapshot { contentId, generatingSystem, externalId, consumableUrl, metadata: MetadataEntry[] }`.

### Aggregate Design Canvas — `EducationalContent`
- Root = Content; **each record is a concrete version** (`contentId` = version). The *logical*
  content is `(generatingSystem, externalId)`. Owns its `ContentMetadata` (open collection of
  `MetadataEntry`).
- **Invariants:** unique `(generatingSystem, externalId, version)`; `consumableUrl` present;
  metadata valid against the `MetadataSchema` of its type (if it exists). The domain does not reference
  concrete keys (see ADR-0001).
- **Commands → events:** `RegisterContent→ContentRegistered`,
  `UpdateContentMetadata→ContentMetadataUpdated`.
- **MVP realization:** seeded schema `learnpack-v1 = {learningObjectives, targetAudience,
  prerequisites}`; metadata by hand; `version` default `"1"`; no lessonPlan (evaluators
  receive the full course). See ADR-0005.

## Evaluation Orchestration (supporting) · refined (see ADR-0002)

### Bounded Context Canvas
- **Purpose:** orchestrate the human effort in an **open and incremental** way — campaigns that
  open with whatever assessors are available and add more over time; assignments with a lifecycle
  (cancel/reassign); detect completion by **submissions threshold**; present the
  metadata to the evaluator.
- **Inbound** — Commands: `OpenCampaign`, `AssignContent`, `CancelAssignment`,
  `ReassignAssignment`, `CloseCampaign`. Reacts to: `EvaluationSubmitted`. Queries:
  `getPendingAssignments(assessorId)`, `getCampaignProgress(campaignId)`.
- **Outbound** — Events: `CampaignOpened`, `AssignmentCreated`, `AssignmentOpened`,
  `AssignmentCancelled`, `ContentEvaluationCompleted`, `CampaignClosed`.

### Aggregate `EvaluationCampaign` (config + scope; open-ended)
- **Description:** configuration and scope of an evaluation effort. Does **not** own the
  assignments transactionally.
- **Invariants:** published, fixed `rubricVersion`; fixed `requiredEvaluationsPerContent` (threshold N,
  typ. 2–3); non-empty `contentSet` to open; `metadataView`.
- **Lifecycle:** `Draft → Open (accepts assignments and submissions bit by bit) → Closed`.
  **Opening does NOT require having all the assignments.**

### Aggregate `Assignment` (small, own lifecycle)
- **Description:** invitation to an `Assessor` to evaluate a `Content` within a campaign.
- **States:** `Assigned → Opened → Submitted` · `Cancelled`. (Reassign = `Cancel` + new
  `Assign` to another assessor.)
- **Invariants:** at most one **active** (non-cancelled) assignment per
  `(campaign, content, assessor)`; only cancellable if not `Submitted`. **Unit of
  human anti-duplication:** fulfilled with **one** submission; re-submitting on one already `Submitted`
  → 409 (see ADR-0005).
- **Commands → events:** `AssignContent→AssignmentCreated`, `OpenAssignment→AssignmentOpened`,
  `CancelAssignment→AssignmentCancelled`. On hearing `EvaluationSubmitted` (Evaluation context) the
  assignment moves to `Submitted`.

### Quorum = completion threshold over submissions (not provisioning)
- A content is `Completed` in a campaign when `COUNT(assignments of that (campaign,
  content) in status 'submitted') ≥ requiredEvaluationsPerContent`. **Cancelled or incomplete
  assignments do not count**; only submissions count.
- **Policy:** on `EvaluationSubmitted(assessor, content, rubricVersion)` all open assignments of
  `(assessor, content)` with a matching `campaign.rubricVersion` are marked `submitted`;
  for each affected campaign, if the count `≥ threshold` → `ContentEvaluationCompleted`. A single
  evaluation can satisfy several campaigns; reassignments work on their own.
- **Consistency:** **eventual** count/completion (policy over events), not a transactional
  invariant of a large aggregate.

### Open questions
- submission without a prior assignment? (MVP: no — the assignment feeds the pending list).
- over-quorum? (allowed; completes on reaching N; extras are stored).
- change N while the campaign is open? (MVP: fixed).

### MVP realization
Tables `campaigns`, `assignments` (with `status`), `evaluations` (ADR-0003). Pending items and
progress = queries. Completion of `(campaign, content)` = `COUNT(assignments submitted) ≥
required` (see 08 §5); `ContentEvaluationCompleted` can be materialized in a table or view.

## Golden Dataset (supporting)

### Bounded Context Canvas
- **Purpose:** curate the human ground truth — accumulate results, apply coverage, declare
  usable.
- **Inbound** — Reacts to: `ContentEvaluationCompleted`. Queries: `getGoldenReference(rubricVersion)`,
  `getCoverage`.
- **Outbound** — Event: `GoldenReferenceEstablished`.

### Aggregate Design Canvas — `GoldenDataset` (per `(contentSet, rubricVersion)`)
- **Invariants:** each included content with ≥N human evaluations; `usable` when
  `coverage ≥ threshold`.
- **Policy:** `ContentEvaluationCompleted` → covers content; `coverage ≥ threshold` →
  `GoldenReferenceEstablished`.
- **MVP realization:** thin; configurable `threshold` (e.g. ~50 courses or ≥X%).

## Reporting / Projections (supporting-generic)

- **Purpose:** read models (CQRS read side): pending items, scores per course, averages (course /
  evaluator / global), inter-rater agreement.
- **Inbound** — Reads **via query ports** (public.py) of the owning modules (evaluation exposes a
  scores query; orchestration, assignments/progress; content, contents; identity, assessors).
  No aggregate of its own.
- **MVP realization (see ADR-0006):** **composition via query ports + aggregation in Python** — NOT
  cross-module views/JOINs (it would break isolation) nor event-driven CQRS projections (over-
  engineering for supporting-generic; = `[future]`). At MVP scale (~750 scores) the cost is nil;
  use **batch** queries to avoid N+1.
  - **Inter-rater per criterion:** simple dispersion (std dev + mean absolute pairwise
    difference + % exact agreement). Formal (Krippendorff's α) = `[future]` with calibration.
  - **Repetitions by the same assessor:** collapse to **the most recent** per assessor (correction),
    then average across assessors — consistent with the quorum (distinct assessors). Intentional
    automatic sampling (mean per assessor + intra dispersion) = `[future]`.

## Identity & Access (generic)

- **Purpose:** users (admin, evaluators) + simple identification; provides `assessorId`.
- **MVP realization:** simple identification (known link/id; admin flag), no robust auth.
  The identity of the `HumanExpert` (`Assessor`) originates here.

## Modelling of variable metadata (ADR-0001)

Two separate concerns to avoid contaminating the domain:
1. **Intrinsic content metadata** (Content Registry): **open and typed** collection
   (`MetadataEntry`) validated against a `MetadataSchema` per `GeneratingSystem`/type (reference
   data, not code). → "varies by content type".
2. **Campaign view** (Orchestration): `EvaluationCampaign.metadataView` = which keys to
   present/require of the evaluator. → "varies by campaign".

The domain never branches on concrete keys; presentation lives in adapters/UI. Detail and
alternatives in `../adr/0001-open-content-metadata.md`.

## State
Define of the **MVP slice: complete** (Rubric Authoring · Evaluation · Content Registry ·
Orchestration · Golden Dataset · Reporting · Identity). Next: **08 — Code** (MVP
implementation plan + ADRs).
