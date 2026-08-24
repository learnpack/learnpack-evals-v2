# Ubiquitous Language — Glossary (v0, living document)

> Convention: the **entire glossary is written in English** — glosses and discussion included,
> not just the domain and code terms. This glossary is *living*: it changes as we learn in
> Discover / Define. Each term is a candidate `class` / `value object` / `event`.

## Content axis — what is evaluated

- **EducationalContent** (aka `ContentArtifact`) — what is evaluated. A registered content is
  **one concrete version** (identified by `contentId`); the *logical* content is the grouping
  `(PackageFormat, externalId)`. The evaluation target is always a version.
- **Course** — a concrete type of `EducationalContent` (e.g. a LearnPack course).
- **ContentVersion** — version of a logical content. Allows evaluating the same course at `v1`,
  `v2`… (improvement/regression). Logical uniqueness: `(PackageFormat, externalId, version)`. MVP:
  default `"1"`. It references `generatorVersionId` (nullable → `unknown`, but **declared**:
  registration demands a generator version or an explicit `unknown`, ADR-0024) and `briefId`,
  carries **edit provenance** (`pure | human_edited | unknown`) and an optional
  `consumableUrl` (below).
- **PackageFormat** *(formerly `GeneratingSystem`; slice 1 code keeps
  `generating_system` until its migration)* — the **package convention** that an extraction
  adapter knows how to read (e.g. `LearnpackV1`). The *format* axis: it selects the adapter and
  acts as the namespace of the `externalId` (ADR-0005). Distinct from the *examinee* axis
  (`GeneratorVersion`); they can diverge — generator v2.3 and v2.4 may both emit `LearnpackV1`
  packages.
  *(Annotated trigger: if a platform emitted several formats sharing externalIds,
  a separate `SourceSystem` would be born.)*
- **Generator** — the **lineage**: `{id, name}`, what a study means by "this generator", and the
  owner of its `GeneratorVersion`s (ADR-0031). It declares its name and **nothing else** — no
  metadata blob, because that is where the generator internals ADR-0030 §1 kept outside this
  system would come back. It is not a second versioning axis: it groups whole versions, it does
  not version parts of one. The name is **typed once per generator**, at the single act that
  mints a lineage; every later act selects it by id, which is what makes a misspelling
  unrepresentable where registrations are frequent. That minting act is guarded: a name within
  one or two edits of a registered one is refused until the caller **echoes back** the name it
  named — the same lineage under different casing or padding is refused outright, and cannot be
  overridden.
- **GeneratorVersion** *(formerly `GeneratorConfiguration`; the `name` moved to its `Generator`
  in ADR-0031)* — the **declared identity of the
  examinee**: `{id, generatorId, version, optional free-form metadata}`. **Immutable**; a genuinely
  different generator ⇒ new record — and that covers **every step of its workflow**: there is no
  sub-component versioning axis (ADR-0030). It is the accumulation key of generator-level claims
  (ADR-0013) — a symmetry of *role* with `SourceConfiguration`, not of mechanism: here the
  identity is **declarative and unverifiable** (the generator lives outside the system), which is
  why there are no mandatory config fields (they are promoted from the blob to typed fields only
  when something consumes them). The metadata blob carries **optional reference data the version
  declares about itself** — today `changelog`, prose for whoever reads a report; it annotates a
  version and versions nothing, and being part of the declared identity it is **write-once**
  (ADR-0030). The generator's *internals* (prompts, workflow steps, configuration) are **not held
  here at all**; what the generator **produces** is a separate matter and is evidence —
  `ContentPackage` and `GenerationBrief`. `unknown` allowed **but never by default** (ADR-0024): content
  valid for per-content judgments, **excluded** from generator-level accumulation. Silent drift is
  undetectable from the inside — process discipline, and a registered cause in loop B's
  diagnostic taxonomy.
- **ContentPackage** — the **complete** work product the generator delivers for a content:
  a VO of artifacts `{kind, locator, format}` with an **open** `kind` vocabulary (consumable,
  manifest, knowledge-graph, item-bank, … — no enum in the domain). Registration captures the
  package, not just a `consumable_url`; the internal artifacts are usually the best evidence
  (`declared_structured`, ADR-0009). The artifact list is **discovered mechanically** from
  the package source by the registry's intake ACL, which is the sole writer of the `kind`
  labels a format uses (ADR-0027). There may be **generator-level** artifacts (shared
  across contents; they are registered now, profiled when a claim needs them).
- **consumableUrl** — not part of the package: an **optional declaration that a deployed,
  human-consumable instance of a `ContentVersion` exists** (ADR-0028). http(s) when declared,
  `null` when none is. The package's bytes are reached through the artifact locators — a
  serving root is transport, not a deployment — so a content that declares no URL is a
  complete evaluand for automated evaluation and simply cannot be handed to a human evaluator.
- **GenerationBrief** — the generation commission: **its own aggregate, immutable, with identity**
  (`briefId`) that `ContentVersion`s reference — the key to the **paired design** across
  `GeneratorVersion`s (same briefs, new products). Lean content: free text + only the typed
  fields that task variables consume (demand-driven). Absent brief = absent registration (it
  limits paired comparison and leaves alternative explanations unruled-out).
- **ContentMetadata / MetadataEntry / MetadataSchema** — **retired** (ADR-0017 superseded
  ADR-0001; migration 0007 deleted the tables). The declared surface of the evaluand is the
  `ContentPackage`: whatever the platform or generator declares travels as package
  artifacts, never as a side metadata channel. Kept here only so the retired channel is not
  rebuilt.
- **ContentProfile** — the **canonical** representation of what a `ContentPackage` contains
  pedagogically, produced by an extraction adapter per `PackageFormat`. Data keyed by the
  data ids of ADR-0014, each with its `EvidenceProvenance` and **with the shape its
  `DataRequirement` declares** (verified when built — ADR-0020). **It is persisted** (reusable
  across instruments) and carries the **adapter version** in its provenance. Criteria operate
  on the profile, never on the raw content.
- **EvidenceProvenance** — the origin of each extracted datum:
  `declared_structured | declared_in_content | absent`, with a **locator** (verbatim quote +
  location). There is no `inferred`: the engine does not fill in what the content does not say
  (ADR-0009). Distinct from the `Assessor`'s provenance: that one says *who judged*; this one,
  *where the judged datum came from*.

## Criteria axis — what is measured (the "what")

- **PedagogicalFramework** — reference theory that *grounds* (grounding), does not
  contain. Initial set: Merrill (First Principles), Biggs (Constructive Alignment),
  Revised Bloom (Anderson & Krathwohl), SOLO, Schmidt (Coherence), Learning Progressions.
- **PedagogicalDimension** — grouping of qualities (the team's "dimensions").
- **Quality** — granular, assessable pedagogical quality: the **variable of the examinee model**
  (ECD). `Claim`s assert *about* it. `grounded_in` one or more `PedagogicalFramework`
  (N:M relationship). It is the **stable column of the language**: claims and criteria change
  across instrument versions; the `qualityId`s persist and give thematic continuity across lines
  of studies. *(Naming open: perhaps `PedagogicalAttribute`.)*
- **EvaluationCriterion** — the verifiable unit of judgment. With claims (ADR-0013), the criterion
  **evidences claims** and reaches the `Quality` through them — the claim mediates; in the
  human reference instrument the item↔`Quality` relation is direct, one item per quality
  (ADR-0052). It **cites** its grounding (N:M);
  it does not contain it. It declares its `eligible_sources`, the **data it requires** (ids,
  ADR-0014) and `onMissingEvidence` ∈ {`no_evidence` (default), `fail`} — the **consequence** of
  the datum's absence; the **fact** is determined by matching/profile (mechanical, never the
  assessor), and `not_applicable` only arises from capability/conditionals.
  ADR-0010 defines its shape: **verifiable pass condition + enumerated failure modes**,
  outcome `scored (pass/fail) | not_applicable | no_evidence | not_assessed |
  execution_error` (ADR-0018, ADR-0037) — not an appreciation scale. (The 1–5 scale survives
  in the **human reference instrument**, which is **not migrated** to this shape: it is the
  reference instrument of calibration — ADR-0015, ADR-0052.)
- **Rubric** (aka `EvaluationInstrument`) — an ordered, **versioned** set of criteria.
  Interchangeable unit. The human reference instrument is
  `LearnPack Pedagogical Reference v2` (12 items).
  Genesis (ADR-0012): an instrument is born from **purpose + content type** (designed-for);
  frameworks **ground** (warrant), they do not originate. Reusing it on another type = a
  deliberate act, re-binding the task model.
  **Role of the reference instrument (ADR-0015, ADR-0052):** it is not migrated to the
  ADR-0010 shape — it is the **reference instrument** of calibration (layer 1): holistic
  elicitation for the human panel, **one item per `Quality`**, answered as agreement with a
  statement on a uniform 1–5 scale. That grain is what makes ADR-0015 §4's per-claim
  coefficient computable, since a claim asserts about exactly one quality (ADR-0026). Its
  stability is a feature — a reference that changes is no reference — and it is honoured by
  **versioning** it: from its first reference campaign, a version is frozen.

## Evaluation design — the evidential argument (ECD-lite, ADRs 0012–0014)

- **Instrument / InstrumentVersion** — the **central aggregate of design**: one version of the
  complete evidential argument. Root = `InstrumentVersion`; it **owns as VOs** its `Claim`s,
  its `Criterion`s and its **applicability bindings** per `PackageFormat` (designed-for).
  Lifecycle: `Draft (editable, assistable) → Published (locked) → Deprecated`; publishing is
  atomic and **human**. `Published` ⇒ immutable — any change ⇒ new version; `claimId`/`criterionId`
  stable across versions (lineage). **It is "the composite"**: with the instrument owning
  claims + criteria + sufficiency + bindings, the old "rubric preset" needs no name of its
  own (DP28). Relationship to `Rubric`: a slice 1 term that the Instrument supersedes; the
  human reference instrument survives under it (ADR-0015, ADR-0052).
- **Claim** — an assessable, **one-sentence** assertion about **exactly one `Quality`**
  (ADR-0026, checked at publish), with: required evidence,
  warrant (framework) and alternative explanations. Being the only path from a `Criterion` to a
  `Quality`, one claim per quality is what makes that path an attribution rather than a guess; a
  criterion bearing on two qualities evidences **two claims**, and one quality may be asserted by
  several claims. **Two grains:** about a content and about the
  **generator** (accumulated across contents — the central product of internal QA). Evidential
  status: `supported | refuted | insufficient evidence`. Findings are organized **under the
  claim they compromise**. Design runs backwards: claims → evidence → observables →
  extraction requirements (ADR-0013).
- **EvidenceModel** — for each claim: what evidence supports/refutes it, which observables
  constitute it and what **data it requires** (that is where the ids are minted — ADR-0014; the
  "dictionary" is a generated view, not an artifact).
- **DataRequirement** — an id in the demand-side namespace, minted when writing an evidence
  rule that needs a datum without an id. It carries two mandatory things, written in that same
  act: a **definition** (what the datum *means* — ADR-0014) and a **`value_domain`** (what
  *shape* it takes — ADR-0020: `string · number · boolean · string_list · record · record_list`,
  with per-field `nullable`, which means "present and may be null", never "may be missing"). The
  two halves are the contract: adapters declare their capabilities against the id and the
  `ContentProfile` verifies the shape against the value domain.
- **Sufficiency** *(formerly `Assembly` — the ECD term; renamed for clarity in the code plan,
  `design/13-code-qa.md` §7)* — how much evidence is enough **per claim**, decided at design
  time; expressed with the psychometric taxonomy of decision models: `conjunctive`
  (default) · `existential` · `m_of_n`. Anything **compensatory (weights/averages/point
  thresholds) is forbidden** — ADR-0011 one level up. The fine-grained quantifier ("at least
  2 of 3…") belongs to the criterion's `pass_condition`, not to this rule. On the automated path
  it replaces the notion of quorum (the human quorum of ADR-0002 still governs campaigns with
  human evaluators).
- **AlternativeExplanation** — enumerated *in advance* per claim: what would produce the same
  observation without the claim applying (failed extraction, atypical format, ambiguous
  criterion). It formalizes the diagnosis of the improvement loop and the dispute channel.
- **TaskModelBinding** — the **per-content-type** binding, on the instrument's side:
  declared applicability (`designedFor`) + **task variables** that condition the judgment
  (expected level, audience — the `ScoringPolicy`'s "contextual reference") + conditional
  criteria. **Where each datum lives in the format** is NOT here: that is the extraction
  adapter's mapping (Content Profiling). Claims and evidence models are portable; only the
  binding is redone per type — reusing an instrument on a new type = **a new version that adds
  the binding**.
- **EvaluationStudy** — the **commission**: an evaluation round, carrying a `name` and an
  optional `description`. Its *purpose* (initial / regression / comparison) is a typology the
  model names and does not yet build — the word is reserved for it, never for the title
  (ADR-0043 §7) — and it is not built because the recipe's **`GeneratorScope`** already says
  it: a scope naming one version is a measurement of that version, one naming several is a
  comparison, so the arity IS the typology (ADR-0044 §9).
  Lifecycle: `Declared` (named, pins pending) →
  `Prepared` (instrument **and assessor**, each **pinned** once, immutable; set composed) →
  `Open` (set fixed) →
  `SignedOff` (human act; immutable report, never re-issued, always with coverage and
  caveats — the document was readable before the act, so what the signature adds is who
  takes responsibility for it, ADR-0041 and ADR-0043 §8). **Its result is a triple** — dataset × `instrumentVersion` × `Assessor`
  (ADR-0042): the assessor is pinned before opening the way the norm is, only that
  assessor's judgments count, and a study that predates the pin reads by recency with its
  mixture declared in the report. Comparing rounds (`CompareStudies`) requires the same
  `instrumentVersion` **and the same assessor** +
  sets paired by briefs; the "line" is a derived grouping, not an entity.
  **Industry mapping:** see §"Equivalences with the evals industry".
- **EvaluationDataset** *(formerly `EvaluationSet` — final rename for alignment with the
  universal term)* — a VO of the study (not an aggregate): the **recipe** (briefIds — the
  reusable key of the paired design — × the `GeneratorScope`) + the **materialized dataset**
  (contentIds, fixed at
  opening), with stratified composition according to which claims need which variety (content
  module, ADR-0013). Its items are contents, with no *expected output* (that is supplied by the
  human reference, ADR-0015). Distinct from the `GoldenDataset` (which is made of *human
  results*).
- **GeneratorScope** — the recipe's second axis: which generator versions the round measures,
  either **every one the briefs bring** or **exactly these** (a non-empty list). **Declared,
  never defaulted** (ADR-0044 §1, ADR-0024's rule at the other end of the same axis): without
  it a round that means to measure one version silently measures every version that answered
  the same commission. It is the fourth thing opening fixes, and the dataset is always
  `briefs × scope` — contents are never picked one by one, because pairing by brief is what
  makes comparing versions an experiment rather than two samples.

## Source axis — how the judgment is produced (the "how")

- **EvaluationSource** — the single **port** (the *type* of source); it produces the judgment.
  Taxonomy (ADR-0016): **`human | automated`** — the only distinction with a real structural
  difference (humans enter via assignments/UI; automated ones via config + execution). *(The
  earlier types `LLMJudge`/`DeterministicVerifier`/`HybridVerifier` were a spectrum, not
  identities: every automated assessor is code that, per criterion, uses the fitting
  mechanism — with or without an LLM inside. See the equivalences table.)*
  - **human** — internal/external SME. **Two participation modes (ADR-0015):** *reference
    panel* — judges qualities directly by reading the content, without a profile (calibration
    layer 1; holistic elicitation, outside the scope of ADR-0010) · *assessor/verifier
    inside the instrument* — works on the profile, verifying quoted outcomes (layer 2;
    prerequisite of an intact profile).
  - **automated** — a **modular, versioned** software artifact with an internal mapping
    `criterion → executor` (pure code, formulas/indices, LLM calls — an internal detail,
    never identity). **It is owed to an instrument (lineage)**: it declares its **coverage**
    per `criterionId` — mapping ∪ **abstentions**, without overlap (ADR-0018; what is
    abstained derives to `not_assessed`) — and evaluates only versions **ratified** for it
    (ADR-0019: the diff is computed over the lineage, only the delta demands a decision from
    the author; ratifying does not change identity). Humans are not bound to instruments.
- **Assessor** — the *concrete, identifiable, versioned instance* of an
  `EvaluationSource` that actually produces results (the "who/what exactly", vs. the
  "what class" of the type). It is the **key of provenance and of calibration**.
  - `human` → a concrete SME with an **expertise profile**: what they bring, as the roster
    knows it. Declared when they are invited (ADR-0049) and correctable afterwards — it is a
    description read when deciding who evaluates what, never a grant, so it carries none of
    the guardrails a role or a status does. *(In the MVP, the evaluating user IS
    a human `Assessor`.)*
  - `automated` → a `SourceConfiguration` `{name, version, instrumentId, coverage, config}`
    (+ the per-version ratifications, which live apart — ADR-0019).
- **assessor status** — `active | deactivated` (ADR-0051). Whether this assessor still takes
  part. **Deactivating deletes nothing**: their evaluations, the assignments they answered
  and the reports naming them are facts about what happened, and an `Assessor` is the key of
  provenance (the same argument ADR-0033 makes for content). What it withdraws is the future
  — no new work, and no way in. A deactivated admin does not count towards the last-admin
  guard. Only `human` assessors have one: an automated assessor is withdrawn by ceasing to
  declare it in code.
- **Invitation** — the act that **registers a human `Assessor`** (ADR-0049): an admin declares
  an address, a `role` and an `expertise` profile, and the `Assessor` itself is still born at
  that address's **first login** (ADR-0004). It holds no credential and grants nothing by
  existing; the login consumes it **once**, and only while creating the assessor — never for
  one that already exists, which is what keeps authentication unable to escalate privileges.
  Lifecycle `Pending → Accepted | Revoked`; **`expired` is derived** from `expiresAt`, never a
  stored state. At most one pending invitation per address. Only `human` assessors are
  invitable: an automated one has no credential to arrive with (ADR-0016).
- **SourceConfiguration** — the config that defines an automated `Assessor` (ADR-0016).
  Any change — code, mapping, model, prompt, internal threshold — ⇒ *another* `Assessor`
  (calibration does not transfer: invalidation by identity).
- **eligible_sources** — compatibility relationship `Criterion` ↔ `EvaluationSource`, values
  `{human, automated}`: not every criterion admits every source.

## Evaluation & results

- **Evaluation** — one concrete **act** of evaluation (not a unique fact): an `Assessor`
  evaluates a content version using an `InstrumentVersion` (the human reference instrument is
  one). Identity =
  **its own id** (`evaluationId`) + coordinates `{assessorId, contentId (version),
  instrumentVersion (formerly rubricVersion), adapterVersion of the profile,
  occurredAt/attempt}`. There is **no** uniqueness by coordinates: **repetitions** of the same
  `Assessor` are allowed (e.g. an automated assessor run N times to measure dispersion). Human
  anti-duplication lives in the `Assignment`, not here. See ADR-0005 — **intact**. The outcomes
  `not_applicable`/`no_evidence`/`not_assessed` are **derived mechanically** (matching +
  profile + the assessor's registered abstentions, ADR-0018) — so is the absence-derived `fail`
  when `on_missing_evidence='fail'` (ADR-0021), and so is `execution_error`, minted by the
  derivation from the typed failure an executor raises (ADR-0037: raising is not deciding) —,
  never decided by the assessor at runtime; **executed** `scored` demands a quote (the derived
  `fail` has none: its evidence is the profile's `absent` entry).
- **ComputedMetric** (aka `Signal`) — a **raw measurement** produced by
  deterministic/hybrid sources (e.g. FK grade level, cohesion index, alignment cosine,
  Bloom level distribution). **It admits structured values** (distributions, lists),
  not just scalars; concrete shape demand-driven. *It is not an outcome*: it is mapped to a
  `CriterionScore` via the **criterion's pass condition** (ADR-0010 — thresholds are
  part of the evidence rule). Computed by the **assessor**, never by the extraction adapter —
  see `MEASUREMENT.md` for why, for what each measure means, and for the evidence behind each
  threshold.
- **ScoringPolicy** — **dissolved** (Define slice 2): its "map `ComputedMetric` →
  outcome" half now lives in the **criterion's pass condition** (thresholds are part of the
  evidence rule, ADR-0010); its "aggregate/compose" half lives in the per-claim
  **sufficiency** (ADR-0013), under the prohibition of ADR-0011. The entry is kept as
  traceability; slice 1 code may refer to it until its migration.
- **CriterionScore** — the outcome of a criterion on a content (+ optional `Comment`).
  ADR-0010 + ADR-0018 + ADR-0037 shape: `scored (pass/fail) | not_applicable | no_evidence |
  not_assessed | execution_error`, **with the quote that sustains it** (only executed `scored`
  demands it; the absence-**derived** `fail` goes without a quote, with its origin recorded —
  ADR-0021; `execution_error` carries its **cause** `{task, kind, message}` instead). The
  four non-scored states are four causes with four remedies: no capability/conditional
  (`not_applicable`) · datum absent from the content (`no_evidence`) · assessor with no
  executor for the criterion (`not_assessed`) · this run's execution failed on it
  (`execution_error` — a fact of the run, never of the content; re-evaluating replaces it).
  (The 1–5 score survives in the **reference panel** flow — ADR-0015, ADR-0052 — where a
  **null score** is the assessor's abstention: *I could not see enough of this course to judge
  this*. It is not the bottom of the scale, which is an answer and penalises like the
  absence-derived `fail` does.)
- **EvaluationResult** — the set of `CriterionScore`s (+ comments) of an `Evaluation`.
- **QualityJudgment** — the published quality judgment on a content: a **per-criterion
  profile** (never a single aggregated score, ADR-0011) + **coverage** (assessed / not
  applicable / no evidence / no capable assessor / execution failed — ADR-0018, ADR-0037) +
  **provenance** (`assessor` + `assessorCalibrationStatus`). The `assessor` half is read
  through the `Evaluation` that produced the judgment and never stored twice, and it travels
  in both forms — the id and `name:version` — because only the second means anything in
  another store (ADR-0042). With ECD-lite
  (ADR-0013) it is communicated as **claims with evidential status** and findings under each
  claim. Event: `QualityJudgmentPublished`.
- **Finding** — a finding derived from an unmet criterion: what failed, the **quote** (absent
  only in the absence-derived fail, whose failure mode is mechanical — ADR-0021), and the
  suggestion that comes from the declared failure mode (the failure *is* the suggestion).
  **Immutable and derived** from the evaluation; disputes are separate facts *about* a finding,
  which feed the improvement of the instrument — not the score.

- **Fitness** — a **read-side projection for optimization, never a judgment** (ADR-0023): the
  proportion of passed criteria per `Quality`, over a denominator that keeps `no_evidence` and
  the absence-derived `fail` (the generator's omissions) and drops `not_assessed` (an assessor
  limitation), `not_applicable` and `execution_error` (this run's own failure — ADR-0037). A `PedagogicalDimension`'s fitness is the unweighted **mean**
  of its defined qualities; a `GeneratorVersion`'s **pools** the criterion counts across its
  contents. An empty denominator is `undefined`, never `0`. It is the fitness function of the
  genetic-algorithm experiment (individual = `GeneratorVersion`, generation = `EvaluationStudy`;
  the individual stays the **version** — it is what can be *run* — and its `Generator` is what
  groups individuals across generations, ADR-0031),
  it carries its **formula version** and its **coverage** — including which assessors were
  ratified **and which actually judged** (ADR-0042: ratification is instrument-scoped and
  permissive, participation is study-scoped and is what makes the comparability rule
  checkable), since values from different coverages are not comparable — and it **never
  enters a `StudyReport`** (ADR-0011 is untouched: claims and findings remain the product).

## Orchestration & calibration (supporting)

- **EvaluationRun** — **merged into `EvaluationStudy`** (Define slice 2, DP28): the run was the
  mechanism without a why; the study is the why with a mechanism. `EvaluationRunStarted` dies;
  the study events replace it. Entry kept as traceability; slice 1 code may refer to it until
  its migration.
- **EvaluationCampaign** — the human realization of an `EvaluationRun`, **open and incremental**
  (config + scope): it pins `rubricVersion`, `requiredEvaluationsPerContent` (completeness
  threshold, not provisioning) and `metadataView`. It opens with whatever assessors exist and
  adds more; it does **not own the assignments transactionally**. See ADR-0002.
- **Assignment** — an invitation to an `Assessor` to evaluate a `Content` in a campaign; a small
  aggregate with lifecycle `Assigned → Opened → Submitted | Cancelled`. Reassign = cancel + new
  one. **It is the unit of human anti-duplication:** ≤1 active assignment per
  `(campaign, content, assessor)`, fulfilled with **one** submission (re-submitting over an
  already `Submitted` one → 409). See ADR-0005.
- **quorum / requiredEvaluationsPerContent** — completeness threshold **of the human path**
  (ADR-0002): a content is `Completed` when the number of **distinct assessors who submitted**
  a valid evaluation reaches the threshold. Cancelled/incomplete assignments do not count.
  On the automated path "complete" = **coverage**, and per-claim evidence sufficiency is set by
  the **sufficiency** (ADR-0013).
- **GoldenDataset** — the human-labeled reference aggregate, with **its own rule**:
  `usable` when it reaches a minimum coverage (`coverage ≥ threshold`); each content
  requires a quorum of **N=2–3** human evaluations.
- **Calibration** — adjustment/validation of automated sources against the human reference,
  keyed by **`(Assessor, Criterion)`** (not by the abstract type): a concrete configuration is
  calibrated, criterion by criterion.
- **CalibrationProfile** (aka `SourceCalibration`) — the output of calibration: the agreement
  of an `Assessor` with the reference, per criterion. It *qualifies* (does not enable) that
  `Assessor`'s future evaluations, via `assessorCalibrationStatus` in the provenance of the
  `QualityJudgment`.

## Cross-cutting

- **DomainEvent** — a past fact of the domain; the means by which state evolves
  (events-first). E.g. (slice 2 model): `GeneratorRegistered` · `GeneratorVersionRegistered` ·
  `BriefRegistered` ·
  `ContentVersionRegistered` · `ContentProfiled` / `ContentProfilingFailed` ·
  `ExtractionAccepted` · `InstrumentVersionPublished` · `InstrumentDefectIdentified` ·
  `EvaluationCompleted` / `EvaluationSubmitted` · `QualityJudgmentPublished` · `FindingRaised` ·
  `FindingDisputed` · `DisagreementDetected` · `StudyOpened` / `StudySignedOff` /
  `StudiesCompared` · human path: `AssessorInvited`/`InvitationResent`/`InvitationRevoked`/
  `InvitationAccepted` · `AssessorRoleChanged` ·
  `AssessorExpertiseChanged` · `AssessorDeactivated`/`AssessorReactivated`, `AssignmentCreated`/`AssignmentCancelled`,
  `ContentEvaluationCompleted` (quorum) · `GoldenReferenceEstablished` · `SourceCalibrated`
  `[future]`. Killed by Define: `EvaluationRunStarted` (DP28) · `MetricComputed` as an event
  (DP19: it is a row, not an event) · `RubricPublished` → `InstrumentVersionPublished`.
- **Localization** — UI i18n (EN/ES). A concern of the target model; MVP = EN.

## Equivalences with the evals industry

> The ubiquitous language is ours; alignment with the industry matters at the **boundaries**
> (onboarding, tooling, integrations). **Discipline:** in domain docs and code, industry
> terms **do not name domain concepts** — they appear only in adapters (ACL,
> `ARCHITECTURE.md` §3) and in this table. Adoption rule: a standard term only when it does not
> collapse a distinction we pay to maintain.

| Our term | Industry | Note |
|---|---|---|
| `EvaluationStudy` | *experiment* (LangSmith/Braintrust/Phoenix/Langfuse offline) · *evaluation run* (MLflow) | "experiment" is ambiguous across ecosystems (unit vs. **container** in MLflow); the study is richer: purpose, gate, publication, human path, generator level |
| line of studies | *internal benchmark* / history vs. baseline | comparison valid only within the line (pinning) |
| `EvaluationDataset` | *dataset* | adopted — universal term |
| `GoldenDataset` | *golden dataset* | already aligned (human reference) |
| `Criterion` **+** `Assessor` executing it | *scorer* (Braintrust/MLflow) · *evaluator* (LangSmith/Azure) · *metric* (DeepEval/Ragas) · *grader* (OpenAI) · *assertion* (promptfoo) | **five names, no standard** — and all of them fuse the *what* with the *who*; our separation is the precision we do not concede |
| Automated `Assessor` (ADR-0016) | *LLM-as-judge* · automated *scorer/evaluator* · our former `LLMJudge`/`DeterministicVerifier`/`HybridVerifier` | the mechanism (with or without an LLM) is an internal detail of the assessor; `Assessor` (versioned instance with a target instrument) is more precise — the industry does not version judges |
| `Sufficiency` | *evidence assembly / accumulation* (ECD) · aggregation of assertions (promptfoo et al.) | simple, explicit accumulation (ADR-0013), conjunctive/existential/m_of_n taxonomy; the industry's compensatory schemes are forbidden (ADR-0011) |
| `CriterionScore` | *score* (Langfuse's "universal object") | ours carries a quote + an outcome of discrete states (`scored`/`not_applicable`/`no_evidence`/`not_assessed`/`execution_error`) |
| `execution_error` (ADR-0037) | *error* vs. *failure* (xUnit) · per-sample *error* + `fail_on_error` threshold (Inspect AI) · null score excluded from aggregates (Braintrust) | the harness records that the judge could not run — categorically distinct from `fail` and never attributed to the evaluand; our derivation mints it from a typed failure, the assessor decides nothing |
| `Evaluation` (the act) | ≈ *trace with scores* / row of a dataset run | their "run" is at dataset level — **false friend, do not adopt** |
| verification queues (layer 2, ADR-0015) | *annotation queue* | **adopted** as a realization term |
| `StudiesComparison` | *experiment comparison* / *regression testing* | within a line |
| `QualityJudgment` / `StudyReport` | *evaluation results* / scorecard | claims with status — no direct analogue |
| (observability, infra) | *trace* | infrastructure vocabulary (Langfuse/MLflow); no collision with the domain |

## Framework combination — two levels (do not confuse)

- **Design-time synthesis** — an instrument whose claims/criteria are `grounded_in` several
  frameworks (the case of the human reference instrument: 12 statements distill 6 frameworks;
  in the claims model, each claim's warrant cites its frameworks).
- **Runtime composition** — *(superseded by Define slice 2)*: the "composite of rubrics/lenses"
  no longer exists as a separate concept — **the `Instrument` is the composite** (it owns
  claims + criteria + sufficiency + bindings, DP28), and aggregation is set by its
  **sufficiency**, never by a `ScoringPolicy` (dissolved) nor by a single score (ADR-0011).
