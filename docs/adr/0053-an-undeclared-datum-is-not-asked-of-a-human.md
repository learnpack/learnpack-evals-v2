# ADR-0053 — An undeclared datum is not asked of a human, and what the mechanics answers depends on who could have declared it

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Evaluation Orchestration · Evaluation Design

## Context

ADR-0052 §7 decided that an item resting on a datum the course never declared is withheld from
the rater and its value produced by the system — the posture 12-define already takes for
automated executors:

> **Mechanical derivation:** no capability or excluded conditional → `not_applicable`;
> `absent` entry in the profile → `no_evidence` (or `fail` if the criterion declares it).
> **The assessor only judges the judgeable.**

It also said, in one clause, that the derived value *enters the fitness* and penalises,
*"because the generator's omission must penalise (ADR-0023 §2)"*. **Realising it showed that
sentence is wrong twice, and the second error would have put a defect into the record that
does not exist.**

**The fitness is the wrong aggregate.** `fitness.py` computes over `criterion_outcomes` — the
automated table. A human evaluation writes `criterion_scores`, and no projection reads it.
Nothing a rater does, or that is derived on their behalf, has ever reached that number.

**And the case the feature exists for is not an omission at all.** The four items that rest on
a declaration rest on `learning_objectives` and `target_audience`. The **LearnpackV1** adapter
declares no capability for either: the format has nowhere to put them, and ADR-0017 already
settled that the declared surface is the package. So a V1 package produces **no entry** for
those ids — not an `absent` entry — and `ContentProfile.ok()` enforces the difference
(*"declared capability + missing data ⇒ `absent` row; no capability ⇒ no row"*, design 12
invariant 3). `derivation.py` reads it in that order and derives **`not_applicable`**, which
ADR-0023 §2 puts **out** of the denominator. The automated side does not charge a V1 generator
for objectives it had no field to declare, and neither may the human side.

The distinction is not academic here. It is the difference between *this generator omitted
something* and *this format cannot express it*, and the two have different remedies: a better
generator, or a wider adapter.

## Decision

**An item is withheld when the profile settles that its datum is undeclared, and what the
mechanics records depends on whether anything could have declared it. Where the profile
settles nothing, the item is asked.**

1. **Three branches, in the order `derivation.py` uses them.** For each item, over the
   content's most recent **ok** profile and the item's declared `required_data`:

   | the profile says | who could have declared it | the form | the row |
   |---|---|---|---|
   | **no entry** for a required id | nobody — the format has no field (ADR-0017) | withhold | `score = null`, `derived = true` |
   | entry with `provenance = 'absent'` | the course could, and did not | withhold | `score = scale minimum`, `derived = true` |
   | entry with a value | — | **ask** | whatever the rater answers |

   The order matters and it is the automated path's: capability first, absence second. Read
   the other way round, every V1 course would look like a course that omitted its objectives.

2. **No `ok` profile ⇒ every item is asked.** An unknown fact is not an absent datum. A
   content that was never profiled, or whose profiling failed, says nothing about what it
   declares, and withholding on silence would be the same lie in the other direction.

3. **Four states, two columns.** `criterion_scores.derived` is ADR-0021's own column ported to
   the human path, for the reason it was added there: *"`derived` distinguishes in data
   'someone judged it' from 'the mechanics derived it'."*

   | `score` | `derived` | |
   |---|---|---|
   | 1–5 | false | a judgement |
   | null | false | the assessor abstained (ADR-0052 §4) |
   | null | true | the item does not apply to this format |
   | scale minimum | true | the course could have declared it and did not |

   The second derived row carries a **value** rather than a null because the derivation is a
   fact about the content at the moment its profile was read, and ADR-0021 records the derived
   outcome rather than leaving it to be recomputed. The first carries none because there is no
   answer to record: nothing was ever askable.

4. **A derived value is excluded from what humans said.** It is out of the per-criterion
   average and out of the inter-rater dispersion (ADR-0006) — nobody judged it — and out of
   the per-claim validity coefficient (ADR-0015 §4), for the same reason: a content whose
   items were all derived would otherwise contribute a perfect agreement no human produced.
   **It is reported**, though, as its own state: a criterion showing no average for two
   different reasons, with nothing to tell them apart, is the coverage lie ADR-0011 §3
   forbids.

5. **The rule is defined once, and the reason is drift.** The screen decides which items to
   ask and the submit path decides which to derive; if those two sets ever disagree, the
   `Evaluation` aggregate's exact-coverage invariant breaks at the moment a rater presses
   submit. One definition, travelling with the artifact that declares the data — the same
   argument ADR-0020 §3 made for the value-domain grammar.

6. **An item declares the data it is about, under the name the automated instrument already
   uses** (`required_data`). Same demand-side namespace, same meaning; what differs is the
   consequence, and the consequence is this ADR.

7. **`prerequisites` is not declared by any item, deliberately.** Item 2's statement mentions
   prior knowledge, but **no adapter in the repo declares that capability** — so naming the id
   would withhold that item everywhere, for ever. The rater reads the deployed course, where
   prerequisites can sit in prose no profile extracts. An item is bound to a datum only when
   the datum's absence really settles the question.

8. **ADR-0052 §7's second sentence is superseded by clauses 1 and 4 of this one.** The rest of
   ADR-0052 stands as written; §7's decision — withhold and derive — is what this realises.

## Consequences

- (+) A LearnpackV1 course stops putting four unanswerable statements in front of an expert,
  which is what the whole thing is for, and it does it without inventing a defect.
- (+) The human record and the automated record now say the same thing about the same fact:
  *not applicable* where the format cannot declare, *the bottom* where the course did not.
- (+) A shorter form on exactly the courses that deserve one: eight items instead of twelve.
- (−) **Over LearnpackV1 courses, the four objectives-dependent qualities receive no human
  data at all.** They are measurable only on contents whose format declares those ids, so the
  mix of the campaign's dataset now decides how well that family of claims can be validated.
  It is a real loss of coverage and the honest one: the alternative was a number about a
  question the course never answered.
- (−) The two sides of the rule live in two route handlers reading one definition. Nothing
  enforces that a third caller would use it, beyond there being only one function to call.
- (−) A derived row exists that no aggregate reads today. That is deliberate — it is the
  record of what happened to an item, and the coverage a future validity computation will
  need — but it is a value with no consumer, and a reader will ask why.
- (−) `criteria.required_data` binds the human reference instrument to the demand-side
  namespace it had been free of. Renaming or retiring a data requirement now reaches one more
  artifact.

## Alternatives considered

- **One branch: withhold whenever the datum is not present, and record the bottom.** The
  literal reading of ADR-0052 §7. Rejected: it charges every V1 generator with omitting
  objectives its format cannot express, and it contradicts what the automated side derives
  from the identical fact.
- **Withhold only on an explicit `absent`, and ask the item where the format has no
  capability.** Defensible — the rater reads the deployed course and can often answer from the
  intro prose — and rejected because it never fires on the case that motivated the work: V1 is
  precisely the no-capability case. The signal it would preserve has nothing to be correlated
  against, since the automated side is `not_applicable` there.
- **A third column naming the reason.** Rejected: two columns already yield four
  distinguishable states, and a third would let them disagree.
- **Computing the withheld set in a shared kernel module.** Rejected as ceremony at this size:
  a method on the published snapshot is one definition too, and it sits next to the
  declaration it reads.
- **Letting the client mark a score derived.** Rejected without hesitation. A rater cannot
  declare their own answer mechanical, and a field that allows it is a way to launder a
  judgement into a fact.

## References

Corrects ADR-0052 §7 (second sentence); the rest of ADR-0052 stands. Mirrors the mechanical
derivation of `12-define-qa.md` (Pedagogical Evaluation, invariant 2) and its realisation in
`evaluation/domain/derivation.py`, causes (b), (c) and (e). Ports ADR-0021's `derived` column.
Depends on ADR-0017 (the declared surface is the package) for why a format can lack a field,
and on ADR-0023 §2 for which outcomes penalise. Clause 4 applies ADR-0011 §3 (a result travels
with its coverage) and ADR-0015 §4 (the per-claim coefficient). Clause 5 reuses the argument of
ADR-0020 §3.
