# 09 — Align & Discover (second pass: internal generator QA)

> **Snapshot of the current design (Aug-2026)** — closure of DDDSMP steps 1–2, second
> pass (slice 2). Frozen. The always-current truth lives in `../ARCHITECTURE.md`,
> `../GLOSSARY.md`, `../adr/` (0009–0015) and `../../STATUS.md`. Supersedes `01-align.md` and
> `02-discover.md` (historical) for all new work. Full series: 09 → 12.

## Align — the framing

**Purpose: internal QA of educational content generators.** The examinee is **the
generator**; each content is one of its *work products*. It is not a market signal nor
certification: the consumer is the team that produces the content.

- **Generation and regeneration stay OUTSIDE the system.** A registered `ContentVersion`
  comes in; actionable findings come out. The system does not observe whether its findings
  caused a change — it only sees another version appear. Knowing whether they helped =
  **comparing evaluations across versions**, which is a capability we do have.
- **Credibility = traceability, not independence.** The failure mode of internal QA is that
  the team ignores the result; what buys trust is being able to see the **quote** behind each
  finding and discuss it (ADR-0009). *(Deferred risk: if these evaluations were used as an
  outward-facing assertion, the independence problem returns in full.)*
- **Deliverable: judgment + suggestions.** With criteria written per ADR-0010 (pass condition
  + failure modes), **the failure is already the suggestion** — no recommendation engine needed.
- **No ceremonial right of reply; yes a channel for disputing findings** — which feeds
  instrument improvement, never the content's score.
- **Statistical agreement by default** (independent raters + dispersion), **threshold-based
  escalation**; the first purpose of escalation is not to settle the score but to diagnose the
  disagreement — its output is **a finding about the instrument**.

### The genesis triad (ADR-0012)

| Input | Fixes | Example |
|---|---|---|
| **Purpose** | the **scope**: which surface is evaluated | UI/UX out — the generator does not control it |
| **Content type** | the **object**: which elements exist and where | instruments are born *for* a `PackageFormat` |
| **Frameworks** | the **norm**: what should be there even when it is not | without a norm, `no_evidence` is impossible |

Scope rule: **the surface the generator controls is what gets evaluated** (tied to the current
purpose). Hard guard: **the demand side is never derived from the observed supply side** — if
the criteria came from what the content has, absence would stop being detectable.

### The design process (ADR-0013, ECD-lite)

Evidentiary argument chain: **claim ← accumulation ← observables ← evidence
identification ← work product**. Design runs **backwards**: claims → evidence → observables →
extraction requirements. Four adopted pieces: `Claim` as an artifact · **two grains**
(content / generator) · **alternative explanations** up front · **assembly** (how much
evidence suffices, per claim). Report = claims with status
`supported | refuted | insufficient evidence`; findings under the claim they compromise.

## Discover — the two loops

```
  ⟦ generation / regeneration ⟧         ← OUTSIDE the system
              │
   ┌──────────▼───────────────┐    content → package → profile (quoted) → evaluation →
   │  LOOP A — evaluate       │    judgment (claims with status) → findings
   └──────────┬───────────────┘
              │ disagreement · disputes · coverage gaps · supply side without a consumer
   ┌──────────▼───────────────┐    genesis (new type → claims → instrument) +
   │  LOOP B — instruments    │    improvement (diagnosis → revision → new version)
   └──────────┬───────────────┘
              └──────────────► feeds back into loop A
```

**The two loops sit at the same level:** A produces the value (judgments/findings); B maintains
the capability (it is where the domain knowledge lives). A without B degrades; B without A has
nothing to test itself against.

### Loop A phases

1. **Instrument ready** — `InstrumentVersionPublished` (pivotal). Designed per the ECD chain.
2. **Content available** — `ContentVersionRegistered`: the complete **`ContentPackage`**
   (consumables + internal artifacts: manifests, knowledge graph, item bank) + `briefId` +
   `generatorVersionId` + edit provenance.
3. **Profiling** — `ContentProfiled` (pivotal, new): **quoted** canonical evidence (ADR-0009),
   by versioned adapter, accepted by a human act (`ExtractionAccepted`).
4. **Evaluation** — tri-state outcomes per criterion, with quote; exact coverage; `not_applicable`
   and `no_evidence` derived mechanically (never by the assessor).
5. **Findings** — `QualityJudgmentPublished` (claims with status + per-criterion profile +
   coverage) + `FindingRaised` per failed criterion (quote + suggestion).

### Loop B — genesis and improvement

- **Genesis:** new content type → profile samples (non-canonical extras included) →
  enumerate claims → derive backwards → publish an instrument *for that type*.
- **Improvement:** `DisagreementDetected` · `FindingDisputed` · systematic `no_evidence` → diagnosis
  choosing among the **pre-enumerated alternative explanations** (+ cause taxonomy:
  ambiguous criterion · insufficient evidence · failing extractor · knowledge that changed ·
  **unregistered generator drift**) → `InstrumentDefectIdentified` → revision → new
  version. Revision authorship records author + reason + `assistedBy`.

## The user journey (E0–E9) and its structural findings

The full activity journey (commission → register generator → inventory artifacts →
design instrument → accept extraction → compose dataset → execute → reliability before
content → generator report → comparison across rounds) uncovered the concepts the
storming did not see; all incorporated into the model:

- **`GeneratorVersion`** — the examinee's **declared** identity (name + version + free-form
  metadata); immutable; different config ⇒ different examinee ⇒ claims do not transfer (role
  symmetry with `SourceConfiguration`). `unknown` allowed (excluded from accumulation).
- **`GenerationBrief`** — the generation commission with its own identity: the key to the
  **paired design** across generator versions (same briefs, new products).
- **`ContentPackage`** — the multi-artifact work product (the internal artifacts are often the
  best evidence). Generator-level artifacts: registered now, profiled demand-driven.
- **`EvaluationStudy`** — the round with a purpose, reliability gate and publication act;
  **`StudiesCompared`** = the generator's pedagogical regression.
- **`ExtractionAccepted`** + adapter version in the profile's provenance.

## Human reference (ADR-0015) — two modes

- **Reference panel (layer 1):** SMEs judge **qualities directly**, without a profile,
  holistic elicitation. `Rubric v1` is **stabilized as the reference instrument** (not
  migrated). Bought once, reused against all instrument versions (anchor: the qualities — the
  stable column of the language).
- **Assessor/verifier (layer 2):** inside the execution, over the profile, verifying
  quoted outcomes; sampled **annotation queues** (5–10%), prioritized by disagreement.
- Instrument↔reference comparison: **per-claim validity coefficients** (no sums);
  ceiling = human inter-rater (ADR-0006).

## ADRs from this stage

0009 (no inference — quoted evidence) · 0010 (verifiable criteria, tri-state) · 0011 (no
single score) · 0012 (genesis/triad) · 0013 (ECD-lite/claims) · 0014 (vocabulary in evidence
models) · 0015 (human reference in two layers). Supporting research:
`research/qa-evals-landscape.md`.
