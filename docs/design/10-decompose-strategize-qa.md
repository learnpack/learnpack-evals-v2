# 10 — Decompose & Strategize (second pass: internal QA)

> **Snapshot of the current design (Aug-2026)** — DDDSMP steps 3–4, second pass. Frozen.
> Supersedes `03-decompose.md` and `04-strategize.md` (historical) for all new work.
> Series: 09 → 12. *(06 — Organise remains a placeholder: small team, single owner.)*

## Subdomains

| Subdomain | Class | Mission | Reason to change |
|---|---|---|---|
| **Evaluation Design** (ex `rubric_authoring`, widened — loop B) | **Core** | Own the evidentiary argument: claims, evidence models, criteria, assembly, bindings; mint the id namespace (ADR-0014); norm-side reference data; defect diagnosis; assistance port | What we assert, or how it is recognized, changes |
| **Pedagogical Evaluation** (existing, reformulated) | **Core** | Execute the argument: per-content judgment, findings, agreement facts | How a judgment is produced/recorded changes |
| **Content Profiling** *(new)* | Supporting (interpretive ACL) | Raw packages → **quoted** canonical evidence; adapters per `PackageFormat`; capabilities; acceptance | How a format is *read* changes |
| **Evaluand Registry** (ex `content_registry`, widened) | Supporting | The examinee and its products: `GeneratorVersion`, `GenerationBrief`, `ContentVersion`+`ContentPackage` | New generator/format/source datum |
| **Evaluation Studies** *(new — the commission)* | Supporting (deliberately thin) | The round with a purpose: dataset, pinning, gate, publication, generator report, comparison | A round's business questions change |
| **Evaluation Orchestration** (narrowed) | Supporting | Coordinate **human effort** (reference panel campaigns; annotation queues) — ADR-0002/0005 intact | How people are organized changes |
| **Golden Dataset** | Supporting | Human ground truth + **instrument calibration reference** (ADR-0015) | — |
| **Reporting** | Supporting-generic | Read models (ADR-0006) | — |
| **Identity** | Generic | — | — |
| **Calibration** | Supporting `[future]` | Calibrate assessors vs. reference, per `(Assessor, Criterion)` | — |

## Events each subdomain owns

- **Evaluand Registry:** `GeneratorVersionRegistered` · `BriefRegistered` ·
  `ContentVersionRegistered` · `ContentMetadataUpdated` · `GeneratorArtifactRegistered`.
- **Content Profiling:** `ContentProfiled` · `ContentProfilingFailed` · `ExtractionAccepted`.
- **Evaluation Design:** `ClaimDefined` · `CriterionDefined` · `DataRequirementMinted` ·
  `InstrumentVersionPublished` · `InstrumentDefectIdentified` · `InstrumentDeprecated`.
- **Pedagogical Evaluation:** `EvaluationCompleted`/`EvaluationSubmitted` ·
  `QualityJudgmentPublished` · `FindingRaised` · `FindingDisputed` · `DisagreementDetected`.
- **Evaluation Studies:** `StudyDeclared` · `InstrumentPinned` · `StudyOpened` ·
  `StudyPublished` · `StudiesCompared`.
- **Orchestration:** `CampaignOpened` · `AssignmentCreated/Opened/Cancelled` ·
  `ContentEvaluationCompleted` (human quorum) · `CampaignClosed`.
- **Golden Dataset:** `GoldenReferenceEstablished`.

## Flow between subdomains (events + queries only — ARCHITECTURE §3)

```
Evaluand Registry ──ContentVersionRegistered──► Content Profiling ──ContentProfiled──► Pedagogical Evaluation
                                                                                            │
Evaluation Design ──InstrumentVersionPublished──► (Evaluation · Studies)                    │ QualityJudgmentPublished
      ▲                                                                                     ▼ FindingRaised
      │  DisagreementDetected · FindingDisputed · coverage gaps · informal supply       Evaluation Studies ──► generator report
      └──────────────────────────────── (loop B) ◄──────────────────────────────────────────┘
Orchestration (human) ◄──reacts to EvaluationSubmitted── · feeds Golden Dataset · Reporting reads via query ports
```

- **Matching** (expected coverage + unmet demand) is a **composed query** —
  Design owns the demand side (ids), Profiling the supply side (capabilities). No state of its own.
- **Study lines dissolve the results↔instrument-version tension:** the study pins
  instrument + brief recipe; comparison is valid **within a line**; new instrument ⇒ new
  line (re-evaluating the baseline if comparison is wanted). Published results are never
  re-emitted.

## Decomposition decisions

1. The generator is **not** its own subdomain: it lives in Evaluand Registry (config, brief and
   package arrive together at intake; a single reason to change).
2. Evaluation Design **includes loop B's diagnosis** (whoever wrote the claim and its
   alternative explanations is the one who chooses among them).
3. Evaluation Studies is its **own** subdomain (lifecycle and decisions: compose dataset, gate,
   compare) — neither Reporting (views without decisions) nor Orchestration (effort, not commissions).
4. **Evaluation emits the agreement/dispersion facts** (it owns the evaluations); Studies
   consumes them for the gate, Design for the diagnosis. No cross-commands.
5. **Generator-level accumulation lives in Studies** (it is the commission's report); first
   realization with ADR-0006-style composition.

**Deltas vs. the slice 1 code:** `rubric_authoring` → Evaluation Design ·
`content_registry` → Evaluand Registry · new `content_profiling` and `evaluation_studies` ·
`evaluation`/`orchestration`/`golden_dataset`/`reporting`/`identity` remain (orchestration
narrowed to the human path).

## Strategize — Core Domain Chart

| Subdomain | Class | Differentiation | Complexity |
|---|---|---|---|
| Evaluation Design | **Core** | high | high |
| Pedagogical Evaluation | **Core** | high | medium-high |
| Content Profiling | Supporting | medium (high potential) | medium |
| Evaluation Studies | Supporting | medium-high | medium-low |
| Evaluand Registry | Supporting | low-medium | low-medium |
| Orchestration | Supporting | low-medium | medium |
| Golden Dataset | Supporting | medium-high | medium |
| Reporting | Supporting-generic | low | low |
| Identity | Generic | low | low |
| Calibration `[future]` | Supporting | medium (high potential) | high |

**Recorded strategic decisions:**

1. **The differentiating knowledge lives in Evaluation Design** — it rises from "secondary Core"
   (original chart) to full core: what used to be thin CRUD became the owner of the argument.
2. **Profiling is supporting *deliberately*** (the same move the original chart made
   with Calibration): it enables determinism, but it **serves** the core. A sophisticated
   Profiling is a sign of over-investment in translation.
3. **Studies is supporting even though it delivers the product**: the richness is in what it
   carries, not in its structure. A complicated `Study` is a smell.

**Investment guide:** rich model + invariants + domain tests in Design and Evaluation ·
pragmatic and thin in Studies, Profiling (**the investment goes to fixtures, not model**), Registry,
Orchestration/Golden/Reporting · buy/trivial in Identity.

**First increment of slice 2:** the core bit by bit with minimal supporting — Design with few
real claims · Profiling with **one** adapter (`LearnpackV1`) · Evaluation through the minimal
automated path · Studies thin. The human path is untouched until the new instrument
exists; the reference panel (ADR-0015) uses the existing machinery.
