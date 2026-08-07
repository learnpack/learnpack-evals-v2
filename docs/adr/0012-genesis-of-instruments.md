# ADR-0012 — Genesis of instruments: purpose and content originate; frameworks ground

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Rubric/Instrument Authoring ·
Pedagogical Evaluation

## Context

Where an evaluation instrument comes from was not defined. The implicit reading of the design
docs (frameworks → dimensions → qualities → criteria) suggested a theoretical origin: first the
pedagogical framework, from there the criteria. With the purpose fixed —internal QA: evaluating
AI-generated content to improve the generating system— the question became concrete: when a new
content type appears, what guides the design of the instrument?

The exploration showed two symmetric failure modes:

- **Theory-first design**: produces instruments unanchored from the evaluand. The industry does
  not do it: nobody publishes "the Bloom rubric" — EdReports builds its review tools **per subject
  and grade level**, k12-teacher-skills **per artifact type**, Quality Matters **per course type**.
  In evaluation theory, validity is not a property of the instrument but of its **use for a
  purpose** (Messick).
- **Offer-first design** (criteria derived from what the content *has*): destroys
  `no_evidence` (ADR-0010). A criterion "are there assessment activities?" would never exist for a
  generator that never produces them — and that is precisely the most valuable finding.

## Decision

**An instrument is the intersection of three inputs with distinct, irreducible roles:**

| Input | Fixes | Example |
|---|---|---|
| **Purpose** | the **scope**: which surface is evaluated | UI/UX out — the generator does not control it |
| **Content type** | the **object**: which elements exist, where they live, what shape they have | instruments are born *for* a type |
| **Frameworks** | the **norm**: what quality is and what *should* be there even if it is not | without a norm, `no_evidence` is impossible |

1. **Scope rule:** what is evaluated is **the surface the generator controls**. Tied to the
   current purpose (internal QA); if the purpose changes (e.g. evaluating third-party content),
   the rule is revised with it.
2. **Instruments are designed *for* a content type** (*designed-for*). Reusing an
   instrument on another type is a **deliberate act** —analogous to revalidating a psychometric
   instrument in another population—, never a default. The technical realization of designed-for
   is the *task model binding* (ADR-0013), not tying the whole rubric.
3. **Frameworks are grounding (warrant), not origin.** They license the inference "this thing I
   measure is quality"; `groundedIn` is kept with that meaning. They help identify what to
   evaluate and how; the criterion's reason for existing is the content to be evaluated.
4. **Hard guard:** the data demand is **never derived from the observed supply**. The normative
   arrow (frameworks) must remain independent of the content, or a real defect of the
   generator gets silently laundered.

## Consequences

- (+) It explains and consolidates a decision already made: the rubric v1 scope "excludes
  presentation and ecosystem" was this scope rule, applied without naming it.
- (+) Instrument design **starts by looking at real content** (profiles of representative
  content). The `ContentProfile` viewer is the designer's workbench — for domain reasons.
- (+) The portable portion of an instrument is delimited: claims and evidence models can be
  type-agnostic; only the binding is re-bound (ADR-0013).
- (−) More instruments are born (per content type). Mitigated by the portable portion and the
  base + overlay pattern (k12: `shared.csv` + file per subject).
- (−) Every new instrument requires making its purpose and its designed-for explicit.

## Alternatives considered

- **Frameworks as origin** (implicit status quo) → rejected: no precedent in the industry,
  and it contradicts the relativity of validity to use.
- **Criteria derived from the content's supply** → rejected: it eliminates `no_evidence` and with
  it the ability to detect what is missing.
- **Presets orthogonal to content type** (any set of rubrics applicable to
  any type by default) → rejected: the real relationship is *designed-for* + deliberate reuse;
  orthogonality by construction would hide invalid transfers of judgment standards.

## References

EdReports review tools per subject/grade level (https://edreports.org/process/review-tools) ·
k12-teacher-skills `evals/` (https://github.com/anthropics/k12-teacher-skills) · Messick,
validity relative to use · detailed reasoning in `notes/genesis-instrumentos-y-ecd.md`.
