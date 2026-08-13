# ADR-0039 — The brief groups the fitness projection; it is not a grain of it

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies · Evaluand Registry

## Context

ADR-0023 computes the fitness at three grains — content, generator version, study — and none of
them names the brief. That was enough while a study's dataset was one course per commission.

It stops being enough for the use the projection was built for. The genetic-algorithm experiment
generates **several courses from the same brief with the same generator version**, deliberately,
to measure how much a version varies on one commission. Reading that requires the values of those
courses *as a group*: which courses answer the same assignment is the question, and the projection
does not answer it.

The datum is already there and already travels. `ContentInfo.brief_id` reaches `compute_fitness`
from the registry gateway, and the study report has labelled each content with its `briefId` since
block 7. The projection is the only per-content view that drops it.

Two facts about a brief's identity decide the shape of the fix.

- **`briefId` is a UUID minted at registration.** It means nothing outside the store, and — the
  part that matters for this consumer — it does not survive a local database being reset and
  refilled, which is a normal act while running generations on a laptop. The same commission
  registered into a fresh database gets a different id.
- **`brief_hash` does survive.** ADR-0022 §3 defines it as `sha256(description + "\n" +
  materialsHash)`, the identity of the effective instruction, unique-constrained and looked up
  before minting. Same commission, same hash, in any store. It is nullable, because a manually
  registered brief has no derived identity. It is persisted, and it was not published: the
  registry's `BriefDTO` never carried it.

## Decision

**Every content section of the projection carries its `briefId`, the header names the briefs the
study was computed over, and no value is aggregated per brief.**

1. **The content grain is labelled.** Each content section carries `briefId`, `null` when the
   intake derived none — the absent brief of ADR-0022 §4 is a first-class recorded state and is
   reported as itself, never as a group of its own.

2. **No brief grain is computed**, and the two poolings that could be are rejected for different
   reasons. *Per brief across generator versions* would mix individuals: the individual is the
   `GeneratorVersion` (ADR-0023, ADR-0031), so a number averaging several of them answers no
   question the GA asks. *Per brief × generator version* is well-defined and still rejected,
   because pooling collapses exactly the dispersion the repeats exist to measure. The asymmetry
   is the argument: a consumer can derive the pooled value from labelled content-grain counts,
   and cannot derive the dispersion from a pooled one. An aggregation that destroys information
   belongs to the consumer, not to the projection.

3. **The header publishes a brief table, one entry per brief:** `briefId`, `briefHash` and the
   brief text. Per brief and not per content, because with N repeats of a commission an inlined
   text is N copies of the same paragraph. The table covers the **union of the study's recipe
   (`brief_ids`) and the briefs its contents reference**, so a commission that produced no course
   — a failed generation — appears with no courses under it instead of vanishing from the reading.

4. **The hash is published because the id is not portable.** It is what lets a consumer keep a
   series across stores, and what lets a human recognise a commission at all. `BriefDTO` and the
   studies-side `BriefInfo` gain the field; nothing else about the brief is exposed.

5. **`fields` stays out.** `promptRecorded` and `origin` are the completeness caveat of ADR-0022
   §5, and the study report already publishes them as `briefCompleteness`. A caveat about what a
   pairing may be attributed to is a reader's concern; the fitness is a gradient, and duplicating
   the caveat into it would put two sources of one truth in two payloads with different
   lifecycles.

6. **`FITNESS_FORMULA_VERSION` stays `"1"`.** Nothing about the arithmetic changes: no state
   enters or leaves a denominator, no value moves, and every number already computed stays
   comparable with every number computed after this. Labels are not formula.

## Consequences

- (+) A GA script groups by commission, and computes variability across repeats of one, from a
  single response — no second call, no join against the store.
- (+) The console can show the repeats of a brief beside each other, which is the only reading
  that makes generator variability visible to a human.
- (+) The hash gives the grouping a key that outlives a local database, which the UUID does not.
- (−) The projection now needs the briefs of a study, so both callers (the endpoint and
  `show-fitness`) gather them — the same five lines `PublishStudy` already runs for the report.
  Composition on read gets marginally more expensive; ADR-0023 §10's reasoning against caching is
  unchanged.
- (−) A content whose intake derived no brief groups nowhere and is reported as such. Making it
  group is a brief-intake question (ADR-0022), not a fitness one.
- (−) The brief text enters a payload that is otherwise all numbers and ids. It is bounded (one
  entry per commission, not per course) and it is the only thing that makes the grouping legible.

## Alternatives considered

- **A pooled fitness per brief** → rejected: see clause 2. It is also the reading most likely to
  be asked for later, which is why the rejection is recorded rather than left implicit.
- **`briefId` alone on each content** → rejected after the first review: it groups correctly and
  identifies nothing. The consumer would have to call `/admin/briefs` to say which commission a
  group is, and the id it grouped by would not match the one it stored last generation if the
  local store was rebuilt.
- **The brief text inlined in every content section** → rejected: N repeats of a commission is the
  normal case here, so the normal case is N copies of one paragraph.
- **The hash on the content grain instead of a header table** → rejected: it is a 64-character
  string per course to avoid a lookup by a key that is already there, and the text would still
  have nowhere to live.
- **Exposing the hash on `/admin/briefs` as well** → deferred, not rejected: nothing asks for it
  there, and the surface that needed it is this one.
- **Deriving the group from the report instead** → rejected: the report is frozen at publish and
  exists only for a published study, while the fitness answers at any status (ADR-0023 §10) —
  which is precisely the moment a GA reads it.

## References

ADR-0023 (the fitness projection: the three grains this refines, the pooling rule of §5 clause 2
argues from, the equal-coverage rule of §7 that labels do not touch, and §9's formula version,
unmoved) · ADR-0022 §3 (brief identity by hash — what makes two courses share a commission, and
the field clause 4 publishes) and §4–§5 (the absent brief, and the completeness caveat clause 5
leaves in the report) · ADR-0031 (the individual is the version — why a pool across versions has
no consumer) · ADR-0011 (no single aggregate score: untouched, this stays outside the report) ·
GLOSSARY (`Fitness`, `GenerationBrief`).
