# ADR-0014 — The data vocabulary lives in the evidence models (no registry of its own)

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Rubric/Instrument Authoring ·
Content Profiling

## Context

Criteria require data from the content ("objectives", "activities"); the per-`GeneratingSystem`
extraction adapters produce them. With N instruments and M formats evolving
separately, both sides must agree on what each datum means ("does the criterion's 'learning
objectives' correspond to the adapter's 'objectives'?").

Solving it with a **pivot vocabulary as a third artifact** was considered — the metadata
registry pattern (ISO/IEC 11179), with SKOS mechanics (prefLabel/altLabel/closeMatch) and the
operational analogue of feature stores: terms entering from both sides (rubrics contributing what
they need, adapters what they find), bilateral governance, a steward. The maintenance cost of that
artifact was an explicit concern.

ADR-0013 broke the symmetry that justified it: the chain *claims → evidence → observables →
data requirements* gives the demand side a **single origin with semantic authority**. There are no
longer two doors to arbitrate.

## Decision

**The dictionary as an artifact is discarded; its function is kept, embedded in the evidence
models.**

1. **Stable ids** for the data that criteria require, minted **only on the demand
   side**, at the moment of writing an evidence rule that needs a new one. The definition of the
   term is written as part of the criterion's authoring — work that ADR-0010 already requires
   (declaring the pass condition and required data).
2. **Matching is by id identity, never by string comparison.** The question "is this field
   that concept?" is answered exactly once, by a human, when writing the adapter's mapping.
3. **Uniqueness** is controlled in the instrument's design review (search before minting;
   same meaning → alias; similar-but-different → new id with a note on why). Verifiable
   by lint: duplicate ids with different definitions.
4. **Adapters declare capabilities against those ids.** Matching keeps its two structured
   outputs: **expected coverage** (what portion of an instrument is evaluable over a content
   type, before evaluating anything) and **unmet demand** (criteria without data).
5. **The "dictionary" is a generatable view** — the union of the ids referenced by the active
   evidence rules + the capabilities declared by the adapters — not a curated artifact.
6. **Supply without a consumer degrades, consciously, to domain analysis:** adapters
   may extract extras under **provisional names marked as non-canonical**, visible in the
   profile viewer, with no governance or matching. The canonical id is minted when a claim needs
   them.

## Consequences

- (+) The maintenance cost collapses into work that is already done: no separate curation, no
  steward, no bilateral registration process.
- (+) The concept ≠ representation distinction (the real contribution of ISO 11179) is kept,
  embedded where the definition is written.
- (+) Same spirit as ADR-0001 (open collection validated by schema: config/data, not code),
  one level up.
- (−) The visibility of the content's richness goes from structured to informal. Accepted at this
  scale.
- (−) The single door depends on the discipline of the design review; without it, drift
  returns.

**Triggers that reverse this decision** (recreating the registry as an artifact with governance):

1. Several instrument designers minting ids in parallel without seeing each other (real drift).
2. External consumers of the `ContentProfile` — the vocabulary becomes published language toward
   the outside and needs a life of its own.
3. Definitions of shared observables diverging across instruments.

The way back is cheap and non-destructive: adding governance to ids that already exist (the
classic ISO 11179 move).

## Alternatives considered

- **Independent registry with bilateral minting** → rejected for now: curation cost with no
  present benefit; it was necessary only while neither side had semantic authority, and
  ADR-0013 gave it to the demand side. Reversal triggers documented above.
- **String-based / ad hoc matching** → rejected: the deduplication problem ("learning
  objectives" vs "objectives") returns intact, multiplied by N×M.
- **Adopting LRMI/schema.org as the full vocabulary** → rejected (already analyzed): it is a
  vocabulary of *discovery*, not of *analysis* — it does not cover the internal structure that
  evaluation needs. Its names are taken where they fit, as a reference for settling naming
  discussions.

## References

ISO/IEC 11179 (https://en.wikipedia.org/wiki/ISO/IEC_11179) · SKOS
(https://www.w3.org/TR/skos-reference/) · feature stores as an analogue
(https://feast.dev/blog/what-is-a-feature-store/) · full reasoning in
`notes/genesis-instrumentos-y-ecd.md` and `notes/exploracion-contrato-contentprofile.md`.
