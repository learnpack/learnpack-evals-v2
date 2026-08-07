# 12 — Define (second pass: internal QA)

> **Snapshot of the current design (Aug-2026)** — DDDSMP step 7, second pass. Frozen.
> Supersedes `07-define.md` (historical) for all new work; this doc is **self-contained**
> (it includes the contexts that barely changed). Series: 09 → 12. The exact names and the
> equivalences with the industry: `../GLOSSARY.md`.

---

## Evaluation Design (Core)

### Bounded Context Canvas

- **Purpose:** own the evidentiary argument: design, version, publish and diagnose
  instruments; mint the id namespace (ADR-0014); norm-side reference data
  (frameworks, qualities, dimensions, data requirements); assist authoring via port.
- **Commands:** `DefineClaim` · `DefineCriterion` · `AssembleInstrument` · `PublishInstrument` ·
  `ReviseInstrument` · `DeprecateInstrument` · `RegisterFramework` · `MintDataRequirement`.
  **Assistance port:** `RequestDrafts(purpose, frameworkIds, supply)` → drafts.
  **Queries:** `getInstrument(version) → InstrumentSnapshot` · `getDataRequirements()`.
- **Reacts to (loop B):** `DisagreementDetected` · `FindingDisputed` · patterns of
  `no_evidence` · informal supply → diagnosis → `InstrumentDefectIdentified` → revision.
- **Events:** `ClaimDefined` · `CriterionDefined` · `DataRequirementMinted` ·
  `InstrumentVersionPublished` (carries the snapshot) · `InstrumentDefectIdentified` ·
  `InstrumentDeprecated`.

### `Instrument` aggregate

Root = `InstrumentVersion`; it **owns as VOs** its `Claim`s (statement + refs to qualities +
warrants + alternative explanations + assembly), its `Criterion`s and its **applicability
bindings** per `PackageFormat`. References frameworks/qualities by id (reference data).
Cycle: `Draft (editable, assistable) → Published (locked) → Deprecated`.

**Invariants:**
1. `Published` ⇒ immutable; every change ⇒ new version. `claimId`/`criterionId` stable across
   versions (loop B lineage).
2. Every claim: one-sentence statement · ≥1 `Quality` · ≥1 framework warrant (if
   pedagogical) · ≥1 criterion as evidence · assembly rule · ≥1 alternative explanation
   **specific to the claim** (boilerplate does not count; generic causes → diagnosis
   taxonomy).
3. Every criterion: verifiable pass condition · failure modes · data requirements that
   exist in the namespace · `onMissingEvidence` ∈ {`no_evidence` (default), `fail`} — the
   **consequence** of absence; the **fact** is determined by matching/profile (mechanical);
   `not_applicable` only arises from capability/conditionals, never from the criterion · ≥1 eligible
   source. *(This is the authorized reading that reconciles ADR-0010 §5 with the mechanical
   derivation.)*
4. Publishing requires ≥1 binding (`designedFor`) + invariants 2–3. Atomic. **It does not require
   extraction capability** (the design stays decoupled from the adapters; readiness informs when
   pinning the study).
5. **Nothing produced by assistance enters `Published` without a human act.**

**Revision metadata:** author + reason + `assistedBy` (assistant config).

### Norm-side reference data (small aggregates)

- `PedagogicalFramework` — **thin**: id · name · citations · scopeNote. The assistants'
  corpus does NOT go here: it is adapter knowledge, keyed by framework id.
- `Quality` / `PedagogicalDimension` — id · name · definition · `groundedIn` · `dimensionId`.
- `DataRequirement` — id · **mandatory definition** · aliases · optional value domain (theory
  structures —Bloom levels, unit hierarchies— enter here **demand-driven**,
  citing the framework; no separate type hierarchy) · optional grounding. Uniqueness via design
  review + lint (ADR-0014).

### Qualities lifecycle

Chain: `Framework ←grounded_in← Quality ←asserts-about← Claim ←evidenced-by← Criterion
←requires← DataRequirement`. Created in the seed + **rare** minting during claim genesis. Used
when designing claims and as the **aggregation and reading axis** of reports. They do not appear
in execution. They are the **stable column of the language**: claims and criteria change across
versions; the `qualityId`s persist (thematic continuity across study lines; anchor of the human
reference, ADR-0015).

### Assistance port (`DesignAssistancePort`)

Given (purpose + framework ids + the type's supply), it proposes **drafts** of
claims/criteria/evidence models. LLM adapters = infrastructure in this repo; corpus/prompts =
versioned artifacts of the adapter, keyed by framework id. Hard boundary: draft ≠
published (invariant 5). Trigger to become a subdomain: assistance sessions
acquiring lifecycle/state with rules of their own.

---

## Content Profiling (Supporting — interpretive ACL)

### Bounded Context Canvas

- **Purpose:** translate raw `ContentPackage`s into **quoted** canonical evidence; adapters per
  `PackageFormat`; capabilities against the namespace; reproducibility via adapter versioning;
  acceptance act.
- **Commands:** `ProfileContent` · `AcceptExtraction(packageFormat, adapterVersion)` ·
  `ReprofileBatch(selection)`. **Reacts to:** `ContentVersionRegistered` (profile if there is an
  accepted adapter). **Queries:** `getProfile` · `getCapabilities(packageFormat)`.
- **Events:** `ContentProfiled` · `ContentProfilingFailed` · `ExtractionAccepted`.

### `ContentProfile` aggregate

Root with coordinates `{contentId, adapterVersion}`. It owns canonical entries
(`dataRequirementId` → value + `EvidenceProvenance` with verbatim quote and locator) and
non-canonical extras (marked).

**Invariants:**
1. Every canonical entry references an existing `DataRequirement` (Conformist) and carries
   `EvidenceProvenance`: `declared_structured | declared_in_content | absent` — no `inferred`,
   with a mandatory quote whenever there is a value (ADR-0009).
2. **Immutable.** Re-profiling with another adapter ⇒ new profile; the old one is kept (the
   published judgments reference it).
3. **An `absent` entry ≠ absence of an entry.** Declared capability + content without the datum →
   explicit `absent` (→ `no_evidence`). No capability → no entry (→ `not_applicable` /
   unmet demand). The denominator trap is blocked **by construction**.
4. Extras never use canonical ids; out of contract.

**The adapter is infrastructure**, not an aggregate: `ExtractorAdapter` per `PackageFormat`,
versioned, declared capabilities, **mandatory fixtures** (this context's investment goes
to fixtures, not model). `ExtractionAccepted` per `(packageFormat, adapterVersion)`, repeated
on each version — the human act that enables discarding "failed extraction" as an alternative
explanation. Automatic profiling on registration; **batch re-profiling as an explicit act**
(never a silent cascade: it can invalidate evaluations).

---

## Evaluand Registry (Supporting)

### Bounded Context Canvas

- **Purpose:** the examinee and its products: `GeneratorVersion`, `GenerationBrief`,
  `ContentVersion` + `ContentPackage` + edit provenance.
- **Commands:** `RegisterGeneratorVersion` · `RegisterBrief` · `RegisterContentVersion` ·
  `UpdateContentMetadata` · `RegisterGeneratorArtifact`. Mechanical **intake ACL**; manual
  load still exists. **Queries:** `getContentPackage` · `getAvailableContents(filters)` ·
  `getGeneratorVersion` · `getBrief`.
- **Events:** `GeneratorVersionRegistered` · `BriefRegistered` · `ContentVersionRegistered` ·
  `ContentMetadataUpdated` · `GeneratorArtifactRegistered`.

### Aggregates (three small ones)

- **`GeneratorVersion`** — the examinee's **declared** identity:
  `{id, name, version, optional free-form metadata, createdAt}`. Immutable identity; a genuinely
  different generator ⇒ new registration (declarative discipline — not enforceable). **Silent
  drift is undetectable from the inside**; "unregistered drift" is a standard cause in the
  diagnosis taxonomy. Config fields are promoted out of the blob **only when something consumes
  them**.
- **`GenerationBrief`** — immutable, with identity (`briefId`) referenced by the
  `ContentVersion`s: the key to the **paired design**. Lean content: free text + typed fields
  that task variables consume. Absent brief = registered absent.
- **`EducationalContent`/`ContentVersion`** — uniqueness `(PackageFormat, externalId, version)`
  (ADR-0005 intact) · `ContentMetadata` (ADR-0001 intact) · `ContentPackage` (VO of artifacts
  `{kind, locator, format}`, `kind` **open**) · `briefId` · `generatorVersionId` (nullable →
  `unknown`, excluded from accumulation) · edit provenance
  `pure | human_edited | unknown`.

`PackageFormat` (format → picks the adapter) and `GeneratorVersion` (examinee → accumulates
claims) are **two distinct axes**; the `ContentVersion` carries both. *(Trigger: if a platform
emitted several formats sharing externalIds, a `SourceSystem` would be born.)*

---

## Pedagogical Evaluation (Core)

### Bounded Context Canvas

- **Purpose:** execute the argument over a content; derive findings; publish the judgment
  (claims with status); emit raw agreement facts.
- **Commands:** `EvaluateContent(contentId, instrumentVersion, assessorId)` (automated) ·
  `SubmitEvaluation` (human — ADR-0005 intact) · `DisputeFinding`. **Batch queries:**
  `getJudgments` · `getFindings` · `getEvaluations`.
- **Events:** `EvaluationCompleted`/`EvaluationSubmitted` · `QualityJudgmentPublished` ·
  `FindingRaised` · `DisagreementDetected` · `FindingDisputed`.

### `Evaluation` aggregate

An **act**. Root with its own `evaluationId`; coordinates `{assessorId, contentId,
instrumentVersion, the profile's adapterVersion, occurredAt/attempt}`. Repetitions allowed;
human anti-duplication in the `Assignment` (ADR-0005). It owns the `EvaluationResult` = one
`CriterionScore` (tri-state) per criterion + raw `ComputedMetric`s (which admit structured
values).

**Invariants:**
1. **Exact tri-state coverage:** one outcome for each criterion of the `instrumentVersion` —
   nothing missing, nothing extra. *(Supersedes the "score ∈ [1,5]" invariant of the historical
   07; the 1–5 survives only in the reference panel, ADR-0015.)*
2. **Mechanical derivation:** no capability or excluded conditional → `not_applicable`; `absent`
   entry in the profile → `no_evidence` (or `fail` if the criterion declares it); `scored`
   requires a **quote**. The assessor only judges the judgeable.
3. Immutable upon completion. Valid references (published instrument, existing profile,
   registered assessor).
4. **Complete provenance chain:** `{instrumentVersion, adapterVersion, assessorId,
   contentVersion}` — no exceptions.

**Events per evaluation, not per criterion** (outcomes as rows; no independent per-criterion
consumer). **Agreement thresholds in the assembly** (Design): Evaluation always measures and emits
`DisagreementDetected` when the threshold is crossed. **`ScoringPolicy` is dissolved**: the
metric→outcome mapping = the criterion's pass condition; aggregation = assembly + ADR-0011.

### `QualityJudgment` and `Finding` — derived, immutable

- `QualityJudgment` per `(contentVersion, instrumentVersion)`: claims with status + per-criterion
  profile + coverage + agreement metrics. Shared across studies that pinned the same
  instrument (mirrors "one evaluation satisfies several campaigns", ADR-0005).
- `Finding`: `{claimId, criterionId, quote, failure mode → suggestion}`. `FindingDisputed` =
  a fact recorded *about* a finding, consumed by Design.

**Human participation (ADR-0015):** the *reference panel* mode (direct qualities, no
profile — `Rubric v1` stabilized as reference instrument) stays **outside** instrument
execution; the *assessor/verifier* mode works over the profile (sampled annotation
queues). The profile prerequisite in execution is kept.

---

## Evaluation Studies (Supporting — deliberately thin)

### Bounded Context Canvas

- **Purpose:** the round with a purpose: dataset, pinning, reliability gate, publication,
  generator report, comparison across rounds.
- **Commands:** `DeclareStudy(purpose, desired assertions)` · `PinInstrument` ·
  `ComposeDataset(briefIds/contentIds)` · `OpenStudy` · `PublishStudy` · `CompareStudies(a,b)`.
  **Reacts to:** `QualityJudgmentPublished` · `FindingRaised` · `DisagreementDetected` ·
  `ContentEvaluationCompleted` (human). **Queries:** `getStudyReport` · `getComparison` ·
  readiness.
- **Events:** `StudyDeclared` · `InstrumentPinned` · `StudyOpened` · `StudyPublished` ·
  `StudiesCompared`.

### `EvaluationStudy` aggregate

Root; it owns purpose, pin, **recipe** (briefIds) and **materialized dataset** (contentIds) as
VOs (`EvaluationDataset`). Cycle: `Declared (instrument pending — the cold-start
state) → Prepared → Open → Published`.

**Invariants:**
1. Instrument pinned **once**, before opening, immutable afterwards. Readiness **informs, it
   does not block**.
2. Dataset fixed on open (the human path can fill it incrementally via campaigns).
3. `Published` ⇒ immutable report, never re-emitted. Publishing is a **human act**.
4. The report always carries **coverage and caveats** (insufficient evidence, unresolved
   disagreements, `unknown` exclusions, unaccepted adapters). Publishing with caveats is
   legitimate and visible; **publishing silently, impossible**.

### `StudyReport` — derived, immutable

Per content: claims with status. At generator level: **for each claim, the distribution of
status across the dataset** + **patterns conditioned by task variables** ("vague objectives
*only* in introductory courses"). Never a cross-claim aggregate (ADR-0011 rules). Explicit
generator-grain claims with their own accumulation rule = `[future]`, defined in the instrument.
`CompareStudies` validates compatibility (same `instrumentVersion` + datasets paired by
briefs) → `StudiesComparison`; the "line" is a derived grouping, not an entity.

---

## Contexts that barely change (self-contained — adjustments over the historical 07)

- **Evaluation Orchestration (Supporting):** coordinates **human effort**. `EvaluationCampaign`
  (open and incremental, ADR-0002: pins instrument version, threshold
  `requiredEvaluationsPerContent`, `metadataView`; does not own assignments transactionally) +
  `Assignment` (lifecycle `Assigned → Opened → Submitted | Cancelled`; ≤1 active per
  `(campaign, content, assessor)`; re-submitting over `Submitted` → 409, ADR-0005). Quorum by
  submission threshold (policy over `EvaluationSubmitted`). Uses: campaigns of the **reference
  panel** (layer 1) and **annotation queues** of the verifier mode (layer 2). It never receives
  commands from Studies.
- **Golden Dataset (Supporting):** aggregate per `(contentSet, version of the reference
  instrument)`; each content with ≥N human evaluations; `usable` when
  `coverage ≥ threshold`; policy over `ContentEvaluationCompleted` →
  `GoldenReferenceEstablished`. **Additional role (ADR-0015): instrument calibration
  reference** — the per-claim validity coefficients are computed against it.
- **Reporting (Supporting-generic):** composition via query ports + aggregation in Python
  (ADR-0006); per-criterion inter-rater (simple dispersion); repetitions collapse to the most
  recent per assessor. **No single aggregate score** (ADR-0011 — `overall_average`/
  `global_average` are retired); views grouped by quality/dimension allowed as presentation.
- **Identity (Generic):** users/roles; provides `assessorId`. Unchanged (ADR-0004/0007/0008).

---

## Decision log and deferrals

The 28 decision points of this pass (DP1–DP28), the pre-closure coherence review and their
resolutions are reasoned in ADRs 0009–0015 and summarized above in each canvas. Cross-cutting
pieces:

- **A Claim asserts *about* a Quality; the claim mediates between criterion and quality** (in
  `Rubric v1` the criterion↔dimension relation is direct — it is the reference instrument).
- **No claim library:** portability by copy with lineage (stable `claimId`). Reuse
  over a new type = **new version that adds the binding**.
- **`TaskModelBinding`**: instrument side = applicability + task variables + conditional
  criteria; the "where each datum lives in the format" belongs to the adapter (Profiling).
- **`EvaluationRun` is merged into `EvaluationStudy`**; the "composite/preset" needs no
  name: **it is the `Instrument`**.

**Explicit deferrals to Code (deliberate — do not invent without a plan):** the operational
scheme of the **assembly** (what "sufficient" means: scored criteria, % pass, minimum number of
assessors, agreement threshold) · the concrete shape of the **per-claim validity metrics**
(ADR-0015) · the realization of the **annotation queues** · the concrete shape of structured
value domains.

**First increment — thin/no:** implementation of the assistance port (the model stays; the
LLM adapters do not) · profiling of `GeneratorArtifact` (register yes, extract no) ·
`StudiesCompared` (needs two rounds) · per-edit draft events (the publication event
suffices).
