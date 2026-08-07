# ADR-0023 — The fitness projection: a read-side signal for optimization, per quality, never a judgment

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies ·
Evaluation Design

## Context

The generator is to be evolved by a genetic algorithm: **individual = `GeneratorVersion`,
generation = `Study`** (a pinned instrument over a brief-paired dataset). A GA needs a
**fitness** — a number it can push on, consistently, across generations.

ADR-0011 forbids exactly that number in the product: *"No single score aggregating distinct
criteria is published, neither per content nor globally"*. Its three reasons hold as strongly
today as when they were written: criteria anchored in Bloom, Biggs, Merrill and Schmidt are not
commensurable; an average hides precisely what is actionable; and with multi-state outcomes it is
not even defined — *"any silent choice lies"*.

The fitness escapes those reasons **only for its consumer**, and it is worth being exact about
why. A GA needs a consistent gradient, not a meaningful number; it may encode an arbitrary
weighting **because that weighting is declared, versioned and pinned**, and because its errors
self-correct across generations. A human reading a report has none of those three protections.
The escape is therefore conditional on the number never being presented as a judgment — which is
what this ADR has to guarantee structurally rather than by good intentions.

The substrate exists as of block 7: `criterion_outcomes` with the five states and the ADR-0021
`derived` mark, `quality_judgments`/`judgment_claims`, and studies with datasets frozen at open
and reports frozen at publish.

Two facts about the model shape everything below:

- **Criteria do not reference qualities. Only claims do.** The chain is `criterion →
  criterion.claim_ids → claim.quality_ids → quality.dimension_id`; 12-define states it as *"the
  claim mediates between criterion and quality"*. Any projection onto qualities passes through
  claims, whether or not claims appear in its output.
- **The `quality → dimension` edge is the one link the pin does not protect.** `claim.quality_ids`
  is frozen inside the published instrument version; `qualities.dimension_id` lives in a global,
  mutable, unversioned table (migration 0005), upserted from a seed file. Re-parenting a quality
  is a one-line edit that silently changes the dimension-level reading of every study already
  published.

## Decision

**The fitness is a read-side projection computed on demand over a study's judgments, primary at
the grain of `Quality`, and it never enters a report.**

1. **Criterion grain.** The unit is the `criterion_outcome`, not the claim. At claim grain the
   `insufficient` status merges `no_evidence` (which must penalize) with `not_assessed` (which
   must not) — collapsing the exact distinction the denominator rules exist to make. The
   projection reads `criterion_outcomes`, not `judgment_claims.evidence_basis`, because the
   latter is pre-aggregated per claim and loses criterion identity.

2. **Denominator semantics — the anti-gaming core.**

   | state | in the denominator | why |
   |---|---|---|
   | `pass` / `fail` | **in** | the executed measurement |
   | `no_evidence` | **in**, penalizes | the generator's omission |
   | derived `fail` (ADR-0021) | **in**, penalizes | absence caused by the generator |
   | `not_assessed` | **out** | an assessor limitation, not the generator's fault |
   | `not_applicable` | **out** | no capability / excluded conditional (ADR-0017) |

   `fitness(quality) = pass / (pass + fail + no_evidence)`. Keeping `no_evidence` and the derived
   `fail` inside is the whole point: excluded, evolution would learn that the cheapest way to
   score well is to **produce unevaluable content**.

3. **This deliberately diverges from the QA denominator, and the divergence is by purpose.**
   ADR-0018 §4 puts `not_assessed` **inside** the ADR-0011 denominator: for a *judgment*, a
   criterion nobody could assess is a gap in what we know about the content, and hiding it would
   overstate coverage. For *optimization*, the same row is noise about the assessor, and charging
   it to the generator would make the fitness track our tooling instead of the artifact. Same
   state, two purposes, two treatments — stated here so the next reader does not read it as a bug.

4. **Attribution to a quality is a set of criteria, deduplicated by `criterion_id`.** A quality's
   criteria are all those evidencing any claim that asserts about it. Deduplication makes a
   criterion evidencing two claims of the same quality count **once**, structurally rather than
   by a special rule. A claim asserting about several qualities contributes its criteria **fully
   to each**: splitting `1/n` would make a criterion's weight depend on how many qualities its
   claim happens to mention — an artifact of instrument wording, not a pedagogical fact.

5. **Quality is primary; dimension is derived as an unweighted mean of its defined qualities.**
   A *sum* would grow with how many qualities an instrument happens to cover, so two instrument
   versions would not be comparable — the one thing the GA needs. The two aggregations are
   deliberately different in kind: **qualities are averaged** (they are incommensurable units of
   meaning, so equal weight is a declared choice, not a measurement) while **contents are
   pooled** into one denominator per generator (contents are samples of one population, where
   pooling is the sound aggregation and a mean of means would over-weight a content with almost
   no defined criteria).

6. **A zero denominator is `undefined`, explicitly, and never `0`.** Zero would assert that
   everything measurable failed, when nothing was measurable — the same family of lie the
   denominator rules exist to prevent. A dimension whose qualities are all undefined is itself
   undefined. This is not a corner case: with `structural:1` abstaining on the four judgment
   criteria and LearnpackV1 supplying no objectives, whole qualities are undefined **today**.

7. **Coverage travels with every value, at every grain**, and the study level additionally
   reports **which assessors were ratified** (ADR-0019) and the `not_assessed` totals. Pinning
   the formula is not sufficient for comparability across generations: because clause 2 drops
   `not_assessed`, a fitness computed with one assessor set is taken over a different population
   than one computed after another assessor is ratified. **The GA compares only within equal
   coverage**, and coverage is published beside the value so that rule is checkable rather than
   aspirational.

8. **The instrument freezes its `quality → dimension` map at publish.** A published
   `InstrumentVersion` stores the mapping for the qualities its claims reference
   (`instrument_versions.quality_dimensions`), and the projection reads that, never the live
   table. The pinned instrument becomes self-sufficient: vocabulary churn afterwards cannot
   change the meaning of an already-published study. The scope is deliberate — the fitness
   reports the qualities and dimensions **the instrument measures**; how much of the vocabulary
   an instrument covers is a matching/readiness question, not a fitness one.

9. **The formula is versioned; the version travels with every value.** It is a code constant
   (`FITNESS_FORMULA_VERSION`), not a table: nothing is persisted, so there is nothing to join
   against, and a stored version that no row references would be ceremony. Changing the formula
   means bumping it, and values carrying different versions are not comparable.

10. **On-read, in `evaluation_studies`, on its own endpoint.** The module already composes on
    read from other modules' publics through gateways, and a finished study is immutable, so
    caching would optimize a cost nobody has yet measured. `GET /admin/studies/{id}/fitness` is
    a separate resource from `/report`.

11. **It never enters `study_reports.report`.** Beyond clause 3's mismatched denominators — a
    fitness sitting beside coverage figures computed over a different population is a reader trap
    independent of any philosophy — `study_reports.report` is frozen jsonb: anything put in it is
    permanent in every already-published report. Being wrong inwards is unfixable; being wrong
    outwards is corrected whenever you like. And the fitness exists **to be optimized against**,
    so publishing it as a report's summary line would point humans at a knowingly gameable proxy.
    The UI may show it beside a report in a clearly separated panel labelled as an optimization
    signal; the published artifact stays clean.

## Consequences

- (+) The GA gets a gradient with declared semantics, and the anti-gaming rules are in the
  formula rather than in a convention someone must remember.
- (+) `undefined` makes the instrument's blind spots visible instead of averaging them into a
  number — the projection reports what it could not measure as loudly as what it could.
- (+) Clause 8 turns a latent silent-mutation bug into an impossibility, and it does so for
  every consumer of the instrument, not only this one.
- (−) **A schema change, in tension with how the decision was first recorded.** STATUS framed the
  fitness as needing "no schema change"; that holds for the computation, which persists nothing.
  The frozen vocabulary map is a real column on `instrument_versions`, justified by the pin, not
  by the fitness — the projection is what made the gap legible.
- (−) Already-published instruments have no frozen map, so the migration backfills them from the
  current vocabulary. That backfill is exact **only because nothing has been re-parented yet**;
  the window closes the first time someone edits a `dimension_id`.
- (−) Recomputed on read, the fitness of a study can change if a content is attributed to a
  generator later (ADR-0024) — the same live-read behaviour as an open study's report, and for
  the same reason. Values are therefore quoted with the moment they were computed.
- (−) `InstrumentVersion.publish()` gains a parameter and `known_qualities` is derived from the
  map's keys. Two sources of the same truth would be worse, but the signature and its tests
  change.
- (−) Fitness and QA coverage will disagree on the same study, permanently and by design.
  Clause 3 exists so that disagreement reads as a decision.

## `[future]`

- **Materializing the projection** once a real GA loop measures a cost. The formula version is
  already in every value, which is what a stored one would need.
- **Weights per quality or per dimension.** The mean of clause 5 is a declared arbitrary choice;
  a justified weighting needs data that does not exist yet (ADR-0011's `[future]` says the same
  about criteria).
- **Fitness across studies** (`CompareStudies`, outside the first increment): it needs clause 7's
  equal-coverage rule enforced rather than published.

## Alternatives considered

- **Claim grain** (`supported/refuted/insufficient`) → rejected: `insufficient` merges
  `no_evidence` with `not_assessed`, and a claim with five criteria would weigh the same as one
  with a single criterion.
- **Dimension as the primary grain** (the original framing) → rejected: the `quality → dimension`
  edge is unpinned, so a dimension-primary fitness would have no stable series at all; quality
  first puts the fragility in the derived layer, where it can be labelled.
- **Sum of a dimension's qualities** → rejected: it rewards instruments that cover more
  qualities, which is a property of the instrument, not of the generator being evolved.
- **Counting `not_assessed` in the denominator** (matching ADR-0018) → rejected: it charges the
  generator for our missing assessors, and the fitness would improve merely by ratifying an
  assessor — a gradient pointing at our tooling.
- **Zero for an empty denominator** → rejected: it is the "*if 'no evidence' counts as the
  minimum, absent is confused with bad*" error of ADR-0011 §3, one level up.
- **Splitting a criterion `1/n` across its claim's qualities** → rejected: see clause 4.
- **Persisting the formula version in a table** → rejected: nothing is persisted for it to
  qualify; the constant in the payload carries the same information.
- **Putting the fitness inside the study report as an optional field** → rejected: optionality
  does not remove the anchoring, it makes it inconsistent, and moves the choice to per-report —
  invisible to anyone comparing two studies. That is ADR-0011's *"any silent choice lies"* one
  level up. Routing it into the report at all would need an ADR refining ADR-0011, answering what
  the number means to a reader who is not an optimizer.

## References

ADR-0011 (no single aggregate score — the prohibition this projection stays outside of, and the
source of the denominator reasoning) · ADR-0018 §4 (`not_assessed` **inside** the QA denominator —
the clause this ADR deliberately diverges from, for a different purpose) · ADR-0021 (the
absence-derived `fail`, counted here as a fail) · ADR-0017 (`not_applicable` from unmet demand —
why whole qualities are undefined today) · ADR-0019 (ratification per instrument version — the
assessor coverage clause 7 publishes) · ADR-0024 (declared generator attribution — what makes
generator-level pooling trustworthy, and the `unknownExclusions` habit reused here) · ADR-0006
(composition on read via query ports — the mechanism clause 10 follows) · ADR-0025 (pedagogical
frames — clause 8's frozen map is the snapshot a swappable vocabulary will need) · 12-define
§"the claim mediates between criterion and quality" and 13-code §3.5/§3.7 (frozen snapshots this
ADR builds on) · GLOSSARY (`Fitness`, added by this decision) · STATUS 2026-08-07 (the
decided-pending item this ADR resolves, including its "no schema change" phrasing, refined here).
