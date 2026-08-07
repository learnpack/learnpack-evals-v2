# ADR-0017 — The evaluand's declared surface is the package: content metadata is retired

**Status:** accepted · **Date:** 2026-08 · **Supersedes:** ADR-0001 ·
**DDD context:** Evaluand Registry / Content Profiling

## Context

ADR-0001 created the open, format-typed metadata (`ContentMetadata` + `MetadataSchema`)
in slice 1, **before the package concept existed**: a content was a
`consumable_url` plus metadata, and the assumption was that the LearnPack ACL would feed
those fields mechanically from its API. Two things changed that picture:

1. Slice 2 introduced the **`ContentPackage`** (artifacts of open kind): the complete
   product the generator delivers, from which the extractor derives quoted evidence
   (ADR-0009). The package subsumed the role of "declared surface of the product".
2. The mechanical metadata provider **never existed**. In practice, the only thing that
   could write metadata was a human hand — and the schema moreover **required** it
   (required keys).

The cost materialized: the first real courses were registered with audience and
prerequisites transcribed by hand from the brief's material, and objectives **derived with
AI** — and the instrument judged that metadata as "the course declares", turning real
generator defects into false passes. It is the inference ADR-0009 forbids in the
extractor, coming in through the registration door.

## Decision

**The evaluand's declared surface is the `ContentPackage`. Content metadata is
retired from the model.**

1. Everything the platform or the generator declares arrives as **package artifacts**
   (open kind; an API URL is also a fetchable locator). There is no side channel.
2. `ContentMetadata`, `MetadataSchema`, the `metadata_schemas` table, the
   `contents.metadata` column, the `UpdateContentMetadata` command with its endpoint and
   form, the metadata mapping of the LearnPack ACL and the campaigns' `metadata_view` (the
   human evaluator's context panel — its only live use; evaluators judge from the
   content itself) are removed.
3. The `LearnpackV1` adapter stops reading metadata: its capabilities are limited to what
   the real package offers (`lesson_inventory`, `lesson_bodies`, `lesson_activities`). The
   data requirements for objectives/audience/prerequisites **remain minted** and the
   criteria **keep requiring them**: declared demand without supply.
4. Resulting semantics (12-define inv. 3, second half): no capability → no entry →
   `not_applicable` → those claims fall **outside the denominator**, recorded in
   coverage; matching/readiness (13-code §6) reports the **unmet demand per
   format**. The finding "this generator does not declare objectives" is stated once, at
   the systemic level where it is actionable — not as an identical `fail` repeated in
   every course, which discriminates nothing.
5. Planned evolution: if the generator starts declaring these data, it will be a new
   `GeneratorVersion`, the data will be **in the package**, and reading it will be a new
   `ADAPTER_VERSION` that declares the capability — only then does "capability present
   + data absent ⇒ `absent` ⇒ `fail` per course" become the correct semantics again.

## Consequences

- (+) Contamination of the declared surface becomes **impossible by construction**:
  there is no channel where a human hand or an external AI can "declare on behalf of" the
  course.
- (+) The evaluation semantics tells the truth: claims not evaluable in this format until
  the generator produces the data — visible as coverage/unmet demand, never as
  a pass nor as noisy refutation (ADR-0011 already requires reporting coverage alongside
  the result).
- (+) Less surface: a table, a column, a schema with validation, a command, an endpoint and
  a form die that could only be used to contaminate.
- (−) `cl-objectives-declared` and `cl-audience-declared` remain unevaluated in LearnpackV1
  until the generator declares — it is the real state of the world, not a loss of the
  engine.
- (−) The human evaluator loses the metadata context panel in campaigns (after
  decontamination it was already empty). If human context becomes necessary again, its
  source will be the package/profile, not a hand-typed field.

## Alternatives considered

- **Keeping metadata with discipline** (optional keys + hints + written rule) →
  rejected: without a mechanical provider, the channel has zero present value and real
  present risk; the discipline depends on institutional memory.
- **Closing only the manual-write door** (removing form/endpoint, keeping the channel
  for a future mechanical intake) → rejected: it keeps a table, schema and validation for
  a role the package already fulfills; if the platform declares something tomorrow, it is
  ingested as an artifact.
- **Having the adapter keep the metadata capabilities "just in case"** → rejected: a
  capability with no real place in the format produces uniform `absent → fail` across all
  courses — noise without discriminating power — and hides that the finding is systemic,
  not per course.

## References

ADR-0001 (superseded — its principle "keys live in reference data, not in the domain"
survives in the `data_requirements` of ADR-0014) · ADR-0009 (no inference; absence
is a result) · 12-define §Content Profiling inv. 3 (absent ≠ no entry; no capability
→ unmet demand) · 13-code §6 (matching/readiness) · the real contamination case
that originated this decision is described in the Context.
