# 11 — Connect (second pass: internal QA)

> **Snapshot of the current design (Aug-2026)** — DDDSMP step 5, second pass. Frozen.
> Supersedes `05-connect.md` (historical) for all new work. Series: 09 → 12.

## Context map

| Upstream → Downstream | Pattern | Mechanism |
|---|---|---|
| Evaluation Design → Pedagogical Evaluation | Customer/Supplier + Published Language | `InstrumentVersionPublished` + `getInstrument(version) → InstrumentSnapshot` (self-contained). Evaluation stores **only** `instrumentVersion`. |
| Evaluation Design → Evaluation Studies | Customer/Supplier + **pinning rule** | The study pins one instrument version when it opens, for its whole life. |
| Evaluation Design → Content Profiling | Published Language of the **id namespace** (Profiling = **Conformist**) | Design mints ids + definitions (ADR-0014); each adapter maps its extractions to those ids when written. Never strings. |
| Evaluand Registry → Content Profiling | Customer/Supplier | `ContentVersionRegistered` (package + brief + generator) + `getContentPackage(contentId)`. |
| Content Profiling → Pedagogical Evaluation | Customer/Supplier + Published Language | `ContentProfiled` + `getProfile(contentId) → ContentProfileSnapshot` (data by id + `EvidenceProvenance` + adapter version). |
| Pedagogical Evaluation → Evaluation Studies | Customer/Supplier (subscriber) | Studies subscribes to `QualityJudgmentPublished`, `FindingRaised`, agreement facts; composes its report with batch queries (ADR-0006). |
| Pedagogical Evaluation → Evaluation Design (loop B) | Customer/Supplier (subscriber) | Design subscribes to raw facts (`DisagreementDetected`, `FindingDisputed`) + queries; the diagnosis is internal to Design. |
| Evaluand Registry → Evaluation Studies | Customer/Supplier (query) | Studies composes its `EvaluationDataset` by **selecting** from what is registered. Requesting more generation is human and leaves the system. |
| Orchestration → Evaluation Studies | Subscriber, **wired by the actor** | The admin opens the campaign via UI referencing dataset + instrument version; Studies only observes `ContentEvaluationCompleted`. No cross-commands. |
| (all) → Reporting · Identity → (all) · Orchestration → Golden | unchanged | Conformist via query ports (ADR-0006) · Open Host Service · subscriber. |

## Integration rules

The original five remain intact (async via events · sync read-only queries · **no
cross-commands** · published language per upstream · stable contracts
modulith→microservices). **Three** are added:

1. **Pinning (Studies↔Design).** A study pins exactly one instrument version and one
   brief recipe; instrument evolution never mutates an open study nor re-emits published
   results. Compare only **within a line**; new instrument ⇒ new line.
2. **Namespace.** Every data requirement and every adapter capability references ids from
   Design's namespace. Supply without a consumer stays deliberately **out of contract**
   (non-canonical, informal extras — ADR-0014).
3. **Provenance chain.** Every judgment references `{instrumentVersion, adapterVersion,
   assessorId, contentVersion}`; every finding carries its quote.

## Composed queries (no state owner — ADR-0006 composition)

- **Matching:** demand side (Design ids) × supply side (Profiling capabilities) → **expected
  coverage** + **unmet demand**, before evaluating anything.
- **Readiness:** commission (Studies) × published claims/instruments (Design) × capabilities +
  `ExtractionAccepted` (Profiling) → gap report **per claim** ("claim without criteria" ·
  "criterion without a datum in this format" · "extraction not accepted"). It is the operational
  answer to "are instruments missing?" / "ready?". **It informs, it does not block.**

## Cold start

Chain that precedes every instrument: **commission purpose → claims → evidence models →
criteria → ids → capabilities.** Signals: a study in *Declared* state (instrument pending)
= "instruments missing", with the gap named per claim via readiness. Cold domain analysis
uses the **informal channel**: exploratory extraction with provisional non-canonical
names, **before** demand exists — without reopening speculative minting. Genesis
is demand-driven (claims), but it **feeds on** the informal supply; nothing decisional depends
on the informal channel.

## ACLs — two edges

- **Intake** (Evaluand Registry's edge): external API → `ContentPackage` + origin facts.
  Mechanical, thin.
- **Extraction** (Profiling adapters): raw package → canonical `ContentProfile`.
  Interpretive, one per `PackageFormat`, testable via fixtures (ADR-0009).
- LLM providers (`LLMJudge` adapter in Evaluation): near `[future]`. Observability/evals
  frameworks (Langfuse/MLflow/LangSmith): **likely as infrastructure** (tracing,
  annotation queues, export), **never as model**; name collision covered by code ACL +
  the equivalence table in `GLOSSARY.md`.

## Published language per context

- **Design:** `InstrumentSnapshot` (claims + criteria with pass condition and failure modes +
  evidence models + assembly + task bindings) · id namespace · events.
- **Profiling:** `ContentProfileSnapshot` · declared capabilities · events.
- **Registry:** `ContentPackage`, `GenerationBrief`, `GeneratorVersion` DTOs · events.
- **Evaluation:** `QualityJudgment` (claims with status + per-criterion profile + coverage) ·
  `Finding` · events + agreement facts.
- **Studies:** `StudyReport` · `StudiesComparison` · events.
- **Orchestration:** unchanged.

## Connect decisions

1. Profiling is a **Conformist** of Design's namespace (no shared kernel — it would reopen the
   bilateral governance discarded in ADR-0014).
2. `InstrumentSnapshot` **self-contained** (the slice 1 `RubricSnapshot` pattern, which proved
   to work).
3. **Studies never commands Orchestration** — the human wiring is done by the actor via UI.
4. Supply without a consumer stays **out of contract** — it is the medium of cold domain
   analysis, not leftover data. It would be formalized only via an ADR-0014 trigger.
