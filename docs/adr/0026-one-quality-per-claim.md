# ADR-0026 — A claim asserts about exactly one quality

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design

## Context

ECD-lite (ADR-0013) puts the claim between the criterion and the quality: a criterion
evidences a claim, and a claim asserts about a quality. 12-define states it plainly — *"the
claim mediates between criterion and quality"* — and the model let a claim name **several**
qualities (`quality_ids`, ≥1).

ADR-0023 turned that permission into a measurable cost. The fitness attributes a criterion to a
quality along the only path that exists, `criterion → claim → quality`, so a claim asserting
about N qualities makes **every one of its criteria count fully in all N**. That is not a choice
the projection makes badly; it is the only thing it can do, because **the model holds no finer
information**. Nothing anywhere records which part of a criterion bears on which quality.

Two consequences follow, and neither is visible until someone reads a number:

1. **Qualities sharing a claim are not independent signals.** They differ only through the
   claims they do *not* share. In the first real instrument, `progression-starting-point` and
   `progression-cognitive-demand` shared `cl-course-arc` and reported the same value — a
   duplicated reading presented as two.
2. **A multi-quality claim weighs more in the roll-up.** A dimension is the mean of its
   qualities (ADR-0023 §5), so a claim naming N qualities occupies N terms of that mean while a
   claim naming one occupies a single term. Its influence grows with how it was *worded*, not
   with what it measures.

The alternative fix — attributing criteria to qualities directly — was rejected: it contradicts
the mediation ADR-0013 rests on, and it would ask an author to state the same relation twice.

## Decision

**A claim asserts about exactly one quality.**

1. **Exactly one, enforced.** `InstrumentVersion.publish()` rejects any claim whose
   `quality_ids` does not hold exactly one id. What was a convention anyone had to remember
   becomes a property of every published instrument.
2. **The criterion→claim edge therefore *is* the criterion→quality edge.** Attribution stops
   being an inference. A criterion that genuinely bears on two qualities says so by **evidencing
   two claims** — explicit information the author wrote, instead of a side effect of how one
   claim was phrased.
3. **One quality may carry several claims.** The rule is one quality *per claim*, not one claim
   per quality: a quality is often asserted from more than one angle, and nothing about that is
   ambiguous.
4. **Enforced at publish, not at construction.** Reconstituting a stored instrument stays
   permissive, so versions already in the database remain readable and drafts remain editable
   while being worked on. This is the same gate every other instrument invariant uses — an
   instrument is checked when it is locked, because that is when it starts binding anyone.
5. **The stored shape stays plural** (`instrument_claims.quality_ids` jsonb, `qualityIds` in the
   `InstrumentVersionPublished` payload). A list of exactly one costs nothing to read, and it
   keeps this reversible: if a later decision widens the rule, no migration and no change at any
   boundary.

## Consequences

- (+) The fitness attributes exactly. Every quality's score is built from the criteria whose
  author said they bear on it, and from no others.
- (+) It removes a way of influencing a dimension's score by wording rather than by measuring —
  the same family of problem the ADR-0023 denominators exist to close, one level up.
- (+) It makes authors state something they otherwise leave implicit: *which* quality this
  assertion is about. Where a claim resists being pinned to one, that is usually a sign it was
  two assertions.
- (−) It removes a legitimate shorthand. A claim about a genuinely two-sided property now has to
  be written twice, and its shared criterion listed under both — more text for the same meaning.
- (−) An author only learns at publish. Import stays permissive by clause 4, so a draft can hold
  a claim this rule will reject; the publish error names the claim and its qualities.
- (−) `quality_ids` now has a shape (a list) wider than its rule (exactly one). Clause 5 accepts
  that on purpose; the domain is where the rule is stated and enforced.
- The first real instrument changes: `cl-course-arc` becomes two claims, and its four criteria
  are distributed by which end of the arc they check. It is still a draft, so no published study
  depends on it (STATUS's disposable-instrument convention).

## Alternatives considered

- **A `quality_id: str` field instead of a one-element list** → rejected: it states the rule in
  the type, which is stronger, but it changes the column, the event payload, the DTOs and every
  consumer for a rule the domain already enforces. Same reasoning as ADR-0024's rejected
  `Known|Unknown` value object: a translation at several boundaries for a distinction already
  forced elsewhere. Revisit if the plural shape ever misleads a reader in practice.
- **Rejecting at construction (`Claim.__post_init__`)** → rejected: it would make instruments
  already stored with two qualities unreadable, turning a design decision into a data outage.
- **Rejecting at import instead of at publish** → rejected as the *only* gate: import is a draft
  act, and drafts are deliberately allowed to be incomplete. Publish is where an instrument stops
  being a sketch.
- **Splitting a criterion's weight `1/n` across its claim's qualities** → rejected in ADR-0023 §4
  and rejected again here: it invents precision the instrument never declared.
- **A direct criterion → quality edge** → rejected: it contradicts the mediation of ADR-0013 and
  duplicates a relation the claim already carries.
- **Leaving it to authoring discipline, with readiness reporting it** → rejected: it is the
  weaker half of what this ADR buys, and the repo has twice decided against discipline that
  depends on remembering (ADR-0017, ADR-0024).

## References

ADR-0023 (the fitness projection — the consumer that made the cost measurable, and whose §4
attribution rule this simplifies to an identity) · ADR-0013 (ECD-lite: the claim mediates
between criterion and quality — the design this refines without contradicting) · ADR-0024 (the
precedent for enforcing a rule at its gate rather than in the type, and for distrusting
discipline that depends on memory) · ADR-0017 (the same precedent, stated first) · ADR-0011
(why a dimension's mean must not be swayed by anything other than measurement) · 12-define
§Evaluation Design and 13-code §3.3 (frozen snapshots this ADR amends: they describe a claim as
referencing qualities, plural) · GLOSSARY (`Claim`) · `docs/seed/instruments/learnpack-course-qa-v1.yaml`
(the draft this changes).
