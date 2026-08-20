# ADR-0047 — Two answers about one quality are two claims, and the bar for building is wide

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design

## Context

`cl-course-revisits-what-it-taught` asserted that *the course revisits its earlier content
instead of juxtaposing it*, and two criteria evidenced it: one asking whether later lessons put
earlier concepts to work, one asking whether the assessment reaches back beyond the lesson it
sits in. It is the only claim the drafts lineage has for `coherence-reinforcement`.

Asked of a real draft, that claim gets two different answers. Four independent readers were
each asked, unprompted, whether one draft builds on itself. Each answered **"partially"**, and
each split the same way without being offered the split: cumulative inside a module, rhetorical
between modules. A conjunctive claim can only report the conjunction of those two answers,
which is the least informative thing either of them says — and the draft in question is exactly
the case where the difference is the finding.

**The mechanical reason is what settles it.** A module's opening lesson has no earlier lesson
WITHIN its module to build on; it can only build across modules. A single ratio over all core
lessons therefore averages two populations whose denominators mean different things, and a
draft that is cumulative inside its modules and empty between them lands in the middle,
indistinguishable from one that is mediocre everywhere. Measured on that draft, the failing
lessons were precisely the module openers — 02.0, 03.0 and 05.0, three of the four lessons
whose identifier ends in `.0`.

The claim had already been reported as failing while only half of it was executed, which is how
the shape came under scrutiny at all: the assessor executes the assessment criterion and
abstains from the other, so a conjunctive claim was being answered from one of its two legs.

The second problem is the bar. The criterion asked for a use *"rather than a restatement"*, and
that distinction cannot be measured. Over one draft, two independent readers found the
working-with act in **23 and 29** places while six model runs found it in **0 to 9**. Across the
whole investigation the pattern held in both directions and under three vocabularies: a model
is dependable about **where** the text does something with a concept and undependable about
**which fine category** the doing falls into — the readers' `uses_as_known` comes back as
`re_explains`, unidirectionally, run after run. A criterion resting on that distinction measures
who is reading.

What is dependable is the coarse, locatable fact. Where the text says what a concept **is**:
two independent readers agree 21 of 22, and the models agree with them 95–100 %. It is the most
reliable measurement in the whole investigation, it comes out of the prose without consulting
the generator's plan, and it is the thing the wrong anchor was being taken from — the plan says
a concept belongs to lesson `X.1` while lesson `X.0` already performs the work, so an
introduction read off the plan is wrong exactly where the draft is interesting. Read off the
prose and reduced to `min(position)` in code, it is an anchor rather than a label.

## Decision

**A quality answered two different ways is asserted by two claims; and what counts as building
on earlier material is the wide act — developing a concept, operating with it, or setting a task
on it — decided from a coarse locatable fact plus a deterministic anchor, never from a fine
semantic label.**

1. **Two answers are two claims.** `cl-course-revisits-what-it-taught` becomes
   `cl-modules-build-within-themselves` ("within a module, later lessons put the module's
   earlier material to work") and `cl-course-builds-across-modules` ("later modules put the
   material of earlier modules to work"). Both keep the quality and the warrant of the claim
   they replace. ADR-0026 permits this in as many words — the rule is one quality per claim,
   not one claim per quality — and its own consequences anticipate this case: *where a claim
   resists being pinned to one, that is usually a sign it was two assertions*.

2. **The test for splitting is a denominator, not a taste.** Two facets belong in two claims
   when the populations they range over are not the same population. Here the lesson that opens
   a module is in the denominator of one facet and cannot be in the denominator of the other,
   so a single ratio is an average over two different questions. A claim whose criteria would
   share one denominator stays one claim, however many aspects its statement mentions.

3. **The criteria follow the claims, and one of them moves untouched.**
   `cr-assessment-retrieves-earlier-taught-material` evidences the across-modules claim without
   a word changed: its pass condition already said *"outside their own module"*, so it was
   already evidencing one half of the old claim and not the other.
   `cr-later-lessons-apply-earlier-concepts` is retired and replaced by two criteria, one per
   claim, each stating its own population — lessons that follow the first lesson of their own
   module, and modules after the first thematic one.

4. **The bar is wide, and it is written into the pass condition rather than into an executor
   (ADR-0016 §4).** A lesson WORKS WITH a concept when it develops that concept, operates with
   it as something the learner already has, or sets a task that checks it. What stays out is the
   bare naming, and — deliberately — saying again what the concept is: re-defining is the course
   starting over, which is the opposite of building on itself. The asymmetry is intended. A
   course cannot be asked to explain everything twice; it can be asked not to define anything
   twice.

5. **The narrow reading is rejected on measurement, not on preference.** The wide bar lands
   inside the band two independent readers produce, on both drafts and in every run; the narrow
   one does not, and its verdict moves with which reader is reading. Where two runs of one model
   report the same places and label them differently, the correct repair is to widen what the
   criterion counts until the label stops deciding the verdict — and where they report different
   places, that is recall, which no rewording fixes.

6. **A verdict rests on a coarse locatable fact plus a deterministic anchor.** The extraction is
   asked only for local, observable acts — which lessons state what a concept is, which lessons
   do something with it — each with a verbatim quote. Which appearance is the INTRODUCTION is
   `min(position)` over what came back, computed in code from the delivery order. No ordering,
   no comparison across lessons and no question about the course as a whole is put to the
   model.

7. **This is a version of the lineage, not a fork.** By ADR-0032 §3 the test is whether the same
   thing is being asserted. It is: the quality is `coherence-reinforcement` before and after,
   and no new question was written down. What changed is that one assertion turned out to be
   two.

8. **What this does not decide, named so it is not mistaken for settled.** The recall of the
   use bucket on concepts shaped like skills stays unsolved — the wide bar works there by
   compensation, with the develops and assessed buckets carrying the signal where the use bucket
   collapses. Where the two-thirds bar should sit is underspecified and known to be: two readers
   who agree on every fact land on either side of it. And the open-reading loop that would
   report what no claim asks is designed and unbuilt; it is a separate decision.

## Consequences

- (+) **Each half of the answer is reportable.** A draft that is cumulative inside its modules
  and rhetorical between them now says so, instead of averaging to a verdict that describes
  neither. That is the finding the readers produced unprompted, and the instrument can now
  carry it.
- (+) **The verdict stops depending on which reader is reading.** The wide bar plus the
  definition anchor is stable across models, across effort levels and across repetitions, where
  the narrow bar inverted between two runs of one model at fixed settings.
- (+) **A defect the instrument cannot currently see becomes visible for free.** Definitions
  placed outside where the plan declares them are 0 and 0 on the draft that reads as cumulative
  and 5 and 5 on the one that does not — a deterministic signal that falls out of the same
  extraction at no extra cost. It is not claimed here; it is recorded as available.
- (−) **The lineage retires a criterion id for the first time**, so an assessor's declared
  coverage can no longer be equal to the shipped version's criteria — it is a **superset** over
  the lineage, with a second guard refusing an id no version declares. Otherwise the declared
  set accumulates retired ids and typos and nothing notices.
- (−) **Coverage moves, so fitness computed against v8 and against v9 is not comparable**
  (ADR-0023 §7): one criterion becomes two and the denominator changes. Anyone comparing
  generations across this boundary is comparing different populations.
- (−) **Every assessor of the lineage needs an explicit ratification against the new version**
  (ADR-0019). Both new criteria are abstained on arrival, so the delta resolves without
  confirmation; taking them costs a new assessor identity and no calibration transfers across
  it (ADR-0016 clause 2).
- (−) **The wide bar buys stability with discriminating power.** Three acts count where one did,
  so a course that develops and assesses relentlessly while never operating with anything will
  pass. Accepted, and the reason is stated in clause 5: a narrower bar does not measure the
  course.

## Alternatives considered

- **Keeping one conjunctive claim and reporting the conjunction** → rejected, clause 1. It is
  the cheapest option and it destroys the only interesting reading of a borderline draft: two
  facets that disagree are reported as the worse of the two, with no way to recover which one
  failed. The claim also becomes unfalsifiable in practice, since the module openers guarantee
  a floor of failures that has nothing to do with the course's coherence.
- **Keeping one claim and splitting only the criteria** → rejected, and it is the closest call.
  Two criteria under one conjunctive claim would compute both ratios, but the claim's own
  sufficiency rule then ANDs them back together, so the report says the same undifferentiated
  thing. Sufficiency is where the two would be fused; the split has to happen one level up or
  it does not happen.
- **Keeping the narrow bar — a use rather than a restatement** → rejected, clause 5. It is the
  pedagogically sharper question, and it is the one the readers themselves answer well (96 %
  agreement with each other). It fails on the supply side: six model runs against readers'
  23–29 found 0 to 9, and the error is systematic rather than noisy.
- **A second instrument for conceptual continuity** → rejected, clause 7. Nothing new is being
  asserted and no new question was written down; by ADR-0032 §4 dark or awkward claims are the
  signal for a fork, never the trigger.
- **Building a knowledge graph of the course and deriving continuity from its edges** →
  rejected. The whole course fits in context about ten times over, so there is no retrieval
  problem to solve; no criterion here walks an edge; and entity canonicalization — the
  documented failure mode of LLM-built graphs — would silently invent violations in exactly the
  criterion that motivated the idea, since an unmerged name variant moves a concept's first
  appearance. The evidence is frozen in
  `docs/design/research/concept-continuity-field-runs.md`.

## References

ADR-0026 (a claim asserts about exactly one quality; its clause 3 — *one quality may carry
several claims* — is what licenses clause 1 here, and its own precedent split `cl-course-arc`
for a different reason) · ADR-0010 (criteria as verifiable conditions; §4 — nuance is recovered
with granularity, not with a scale — is the same move at the criterion level) · ADR-0016 §4
(the instrument stays 100 % declarative: the wide bar is normative text, and an executor merely
realizes it) · ADR-0032 §3–§4 (an instrument forks by claim, not by format; the test applied in
clause 7) · ADR-0019 (coverage by criterion lineage and ratification per version — why the
retired id stays declared and why the new version is ratified explicitly) · ADR-0018 / ADR-0021
(`not_assessed` and the fail derived from absence — why abstaining on the two new criteria is
honest rather than a zero) · ADR-0023 §7 (coverage travels with every fitness value and only
equal coverage may be compared — the consequence of retiring one criterion for two) · ADR-0034
(LLM-carrying assessors: semantics are identity — why the calibration dumps that produced this
evidence sit outside the assessor and decide nothing) · ADR-0046 (the sibling precedent: a
version of this lineage that widens what counts as evidence, with the same coverage
consequences) · 12-define §Evaluation Design (frozen snapshot: the claim as the mediator
between criterion and quality — reaffirmed here, not amended) · GLOSSARY (`Claim`, `Criterion`,
`Sufficiency`) · `docs/seed/instruments/course-drafts-qa-v9.yaml` (the two claims and the two
criteria this decision records) · `docs/design/research/concept-continuity-field-runs.md` (the
frozen field runs behind every number quoted above) · `docs/RUNBOOK-calibrating.md` (how the
evidence is produced, and the rule clause 6 states).
