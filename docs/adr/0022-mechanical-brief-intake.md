# ADR-0022 — Mechanical intake of the GenerationBrief at content registration

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

The `GenerationBrief` is the commission's identity on the evaluand axis: paired datasets
(same briefs, different generator versions) are the key of generator-level comparison, and
`ComposeDataset` (13-code §3.6) selects contents **by brief**. Today every content registers
with `brief_id = null` — recorded absent — so no paired dataset can exist, and nothing fills
the brief because entering it by hand would reintroduce the hand-typed side channel that
ADR-0017 removed.

LearnPack's real pipeline is two-stage — (user prompt + attached material) → syllabus →
lessons — and the **original prompt is not persisted**: for already-generated content it is
unrecoverable. What the package does carry is `.learn/initialSyllabus.json`, whose
`courseInfo.description` is the operative instruction during lesson generation and whose
`courseInfo.contentIndex` identifies the attached material.

Two forces shape the mechanism:

1. The brief is **identity, not evidence**: it must not become a profile entry (profiling
   extracts pedagogical evidence from the product; the brief identifies the commission).
2. Pairing must need **no coordination** between registrations: two packages generated from
   the same effective instruction must resolve to the same brief without anyone linking them.

## Decision

**The registry's intake ACL derives the brief mechanically at registration, and hash
identity dedupes.**

1. **Where:** the LearnPack ACL of the Evaluand Registry (`acl_learnpack` + a
   `BriefIntakePort` injected into `RegisterContentVersion`). Never a profiling concern.
2. **What:** for `LearnpackV1`, `brief` = `courseInfo.description` of
   `.learn/initialSyllabus.json`; `fields` = `{origin: "ai_derived_syllabus",
   promptRecorded: false, materialsHash: sha256(canonical courseInfo.contentIndex),
   materialsSource: <declared source if the syllabus carries one>}`. The material itself
   lives in the package — it is not duplicated into the brief.
3. **Identity:** `brief_hash = sha256(description + "\n" + materialsHash)`, persisted in
   `generation_briefs.brief_hash` with a **UNIQUE constraint** (nullable: manually
   registered briefs carry none). Registration looks the hash up first: same effective
   instruction → same hash → same `briefId` across generator versions. The constraint makes
   pairing a database invariant — two concurrent registrations cannot mint two briefs for
   one commission.
4. **Best-effort, non-blocking:** no syllabus artifact in the package → the content
   registers with `brief_id = null` (an absent brief is already a first-class recorded
   state); a fetch or parse failure → logged warning, registered absent. Registration never
   depends on the intake succeeding. An explicit `brief_id` in the command wins over intake.
5. **Declared partial:** the brief registers with its completeness stated —
   `promptRecorded: false` is the datum with which studies place their own caveat: pairing
   holds for "same effective instruction" (lesson stage), **not** for attributing
   differences to the prompt's wording.

## Consequences

- (+) `ComposeDataset` by briefs has real briefs to select; A/B pairing across generator
  versions is automatic, with no coordination protocol.
- (+) LearnpackV2 (native briefs, expected) arrives through the same intake channel with
  better completeness — the mechanism is built once, against V1's partial brief.
- (−) The pairing guarantee is scoped: differences between paired contents cannot be
  attributed to prompt wording while `promptRecorded: false`. Forward note to LearnPack:
  persisting the original prompt in the package (e.g. `courseInfo.originalPrompt`) makes the
  briefs of new content complete; the prompt preprocessor is part of the generator's
  identity and is versioned in `GeneratorVersion.metadata`.
- (−) A silent fetch failure leaves a null brief that a syllabus-bearing package "deserved";
  the log records the attempt, and the studies' `unknown`/absent-brief caveats keep the gap
  visible. If operation shows this soft failure hides real losses, hardening it is one
  `raise` in the intake adapter.
- The fitness-projection ADR announced in STATUS shifts to **ADR-0023**.

## Alternatives considered

- **Brief as a profile entry** → rejected: the brief identifies the commission (evaluand
  axis); profiling extracts evidence from the product. Mixing them re-opens the hand-typed
  metadata channel ADR-0017 closed.
- **Manual pairing (an admin links contents to briefs)** → rejected: coordination that does
  not scale and silently erodes — exactly the accidental-null problem being solved.
- **Dedup by lookup only (no unique constraint)** → rejected: concurrent registrations of
  the same commission could mint two briefs; the constraint turns the invariant into
  structure.
- **Hard-fail intake** → rejected for the first increment: registration would depend on a
  network fetch; a null brief is recorded, visible and caveated, while a failed
  registration loses the evaluand entirely.

## References

ADR-0017 (the declared surface is the package — what closed the metadata channel) ·
13-code §3.6 (`ComposeDataset(briefIds)` — the consumer) · 12-define §Registry
(`GenerationBrief`, absent-is-recorded) · STATUS 2026-08-07 (the agreed two-stage pipeline
analysis this ADR promotes) · GLOSSARY (`GenerationBrief`, `EvaluationDataset`).
