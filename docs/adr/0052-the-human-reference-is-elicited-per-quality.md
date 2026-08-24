# ADR-0052 — The human reference is elicited per quality, as agreement with a statement

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Evaluation Design · Golden Dataset · Calibration `[future]`

## Context

ADR-0015 gave the human panel a job and a shape. The job, clause 4:

> **The instrument↔reference comparison does not sum anything: validity coefficients per
> claim.** Each claim is correlated with the human score of **its** quality across the
> contents of the set — per-claim diagnosis ("which ones track expert judgment"), never sums
> to dimension.

The shape, clause 3: `Rubric v1` stabilized as that reference, `criterion↔dimension 1:1`,
five items on a 1–5 scale. ADR-0026 later made the join clause 4 depends on exact — a claim
asserts about **exactly one** quality — so the single meeting point of the two worlds is the
`Quality`.

**The two clauses do not fit together.** `course-drafts-qa-v9` carries 21 claims over 19
qualities; the form produces five numbers, one per dimension. The four claims of the
objectives family can only be correlated against *the same* human number, so "which ones track
expert judgment" has no answer for any of them. Worse, the two failure modes the panel exists
to tell apart become indistinguishable: *the instrument's criteria for this quality measure
something else* and *this question is not answerable holistically* both show up as one
dimension-level number that disagrees. The per-claim diagnosis is not weak at this grain — it
is arithmetically unavailable.

Three defects of the items themselves compound it, and none is about the grain:

- **Each item is multi-barrelled.** The guidance of `objectives-quality` asks for four things
  at once — clear, measurable, at the right cognitive level, of increasing complexity — which
  are four qualities. The rater averages them mentally and the average cannot be recovered.
- **The anchors carry no information and are identical across all five items**
  (`"not at all / very low"` ↔ `"fully / very high"`). Two raters with the same reading can
  differ by two points purely in how they use the scale, and by clause 5 the human–human
  agreement is the ceiling of everything else, so this is the cheapest measurable thing to
  lose.
- **There is no way to say "I could not judge this".** The automated side abstains through
  `no_evidence` / `not_applicable`; the human is forced to produce a number, which puts noise
  exactly where the other side is silent.

Clause 3 froze v1 on purpose — *"a reference that changes is not a reference"* — but left
*"a light review (anchors, definitions) before the first reference campaign"*, and `STATUS.md`
records that review as still pending. **No reference campaign has ever run.** The stability
that clause protects binds from the first campaign onwards; before it there is no reference to
destabilise, and this is the last moment at which the shape is free.

Two facts about the first campaign settle the rest. The panel will read the **processed,
deployed course** — the artefact a learner gets — while the instrument reads the **draft**;
the processing step only adds files and materialises `code_challenge_proposal` blocks, so the
lesson prose the two sides read is the same text. And the dataset mixes generator versions,
including packages from a version that declares neither learning objectives, nor audience, nor
prerequisites.

## Decision

**The human reference is elicited one item per quality, as agreement with a statement about
what the course does; `Rubric v1` is superseded by `v2` rather than amended.**

1. **The grain is the quality, and the id is the join.** One item per quality, and the item's
   `criterionId` **is** the `qualityId`. Clause 4 of ADR-0015 asks for the human score of a
   claim's quality; after ADR-0026 that is a single value, and making it a primary key rather
   than a lookup is what turns the comparison from a mapping exercise into a join. The
   `dimension` column survives as a grouping for reports and is not shown to the rater: a
   dimension is where qualities are read together, never where they are elicited.

2. **`v2` supersedes `v1`; it does not sit beside it.** Two live reference instruments would
   buy a permanent ambiguity — every coefficient would have to say which reference produced
   it — in exchange for a stability that protects nothing, since no campaign has been run
   against v1. Clause 3 of ADR-0015 is amended in its shape (`criterion↔dimension 1:1`) and
   upheld in its principle: **a reference is stabilised by versioning it, not by never
   improving it.** From the first campaign against v2, clause 3 binds v2 exactly as it bound
   v1.

3. **Twelve items, and the response is agreement with a statement.** A single 5-point
   agreement scale, identical for every item, over positively-worded statements — the rater
   learns the scale once and never changes frame. What v1's shared anchors failed to give is
   moved into each item's `guidance`, which carries an **Agree** half and a **Disagree** half,
   *each standing on its own*: a rater reads one or the other according to where they are
   leaning, never both, so a half written as the continuation of the other is not read at all.
   All statements are positive (5 is always the good end). Reverse-worded items detect
   careless responding and cost measurement artefacts; with two raters per content the trade
   does not pay.

4. **The bottom of the scale is an answer; the abstention is off the scale.** `1` means *the
   course does not do this*, and it is the human counterpart of the penalising outcome the
   automated side derives from absence (ADR-0021, ADR-0023 §2). *"I couldn't see enough of
   this course to judge this"* is a different act, is stored as a **null score**, and is not a
   point on the scale. The distinction is load-bearing rather than cosmetic: an abstention
   recorded where the machine penalises decorrelates the two sides on precisely the contents
   that carry the most information, and a wording that invites "not applicable" collects the
   first meaning under the second.

5. **The twelve are chosen where validity is at risk, not where evidence is abundant.**
   Semantically judged criteria over mechanically computed ones — a deterministic count needs
   its extraction verified (layer 2), not a human correlate — and, deliberately, the three the
   repo has already written down as unresolved: `progression-cognitive-demand`, whose
   `lexical_load` is *"a proxy awaiting calibration against the human reference"*
   (`MEASUREMENT.md`); `coherence-reinforcement`, whose bar ADR-0047 §8 records as
   *"underspecified and known to be"*; and `progression-prerequisites`, where the criterion
   reported zero violations over three drafts while two independent readers found a real
   defect. Spread across the five dimensions so that none goes unvalidated.

6. **The panel judges the processed deliverable, declared as the draft's `consumable_url`.**
   The evaluand stays the draft — one `contentId`, so the human and automated judgements meet
   with no join at all — and ADR-0028's field keeps its meaning: a deployed, human-consumable
   instance of that content exists. Recorded here because it is not obvious from the field:
   the URL does not serve the evaluand's bytes. The lesson prose is identical, so eleven items
   read the same text; **the assessment item does not**, and it carries the confound as a
   declared alternative explanation — the human read a delivered challenge, the instrument
   read a proposal (ADR-0046).

7. **An item whose datum the course never declared is not asked; the value is derived.**
   Where the content declares no learning objectives, no audience and no prerequisites, the
   items resting on them are withheld from the rater and the system produces their value —
   the same posture 12-define takes for automated executors (*"the assessor only judges the
   judgeable"*), for the same reason. Two rules travel with it, and they point in opposite
   directions on purpose:
   - a derived value **enters** the fitness, because the generator's omission must penalise
     (ADR-0023 §2) — this is not `not_applicable`;
   - a derived value is **excluded** from the validity coefficient, because nobody judged it
     and there is nothing to correlate. Included, a content whose items were all derived
     contributes a perfect agreement that no human produced.

   Same state, two purposes, two treatments — stated the way ADR-0023 §3 states its own, so
   the next reader does not read it as a bug. What the rater sees is one neutral line saying
   some items are not shown, naming neither generator nor version: the dataset mixes versions
   and the panel is blind to which produced what.

8. **Realisation.** `response_format` on the reference instrument (`numeric | likert`) is what
   selects the control; `criterion_scores.score` becomes nullable, which is the whole of
   clause 4's storage — a `CHECK (score between 1 and 5)` passes a null unchanged. Clause 7
   needs two more columns (`criteria.requires`, `criterion_scores.derived` — the port of
   ADR-0021's own column to the human path) and a query port into Content Profiling, and lands
   in the increment after this one.

## Consequences

- (+) **ADR-0015 §4 becomes executable.** A claim's quality has its own human number, so
  "which claims track expert judgment" is answerable, and the two failure modes the panel
  exists to separate — *the criteria measure something else* vs *the question is not
  answerable* — are told apart by reading the human–human agreement of the same item.
- (+) Twelve anchored items cost the rater less than five unanchored ones: the scale is
  learned once, and the guidance says what the endpoints mean in terms of what the course does.
- (+) The absence of a declaration stops being a hole. It is an answer at the bottom of the
  scale where the rater can see it (clause 4) and a derived value where they cannot (clause 7),
  and both line up with what the automated side does with the same fact.
- (−) **Coverage of the objectives family is bought with dependence on a declaration.** Four
  of the twelve rest on the course stating what it teaches; over a dataset with many packages
  that declare nothing, those four qualities are judged on a smaller set than the other eight,
  and their coefficients are correspondingly weaker. The mix of the dataset is now a
  measurement decision, not only a sampling one.
- (−) **The reference no longer covers seven qualities that carry claims.** Nineteen have
  claims and twelve are elicited; the rest get no validity coefficient at all. That is the
  price of an instrument a rater can finish, and the choice of which twelve is recorded in
  clause 5 rather than left to whoever writes the next version.
- (−) The assessment item is confounded by the processing step and can only be read with that
  in hand (clause 6). It is kept because dropping it would leave `constructive-alignment` with
  one item.
- (−) **A criterion whose automated side has no variance cannot be validated by any number of
  raters.** `progression-prerequisites` is the known case — zero violations over every draft
  judged so far — and it is kept for what it finds, not for a coefficient it will not produce.
  Running the instrument over the dataset before the campaign is what tells the two apart, and
  nothing in this decision does it.
- (−) Rubric v1 stops being seeded. Rows already in a database survive — seeding upserts and
  never deletes — so campaigns pinned to v1 keep resolving; a fresh database has only v2.

## Alternatives considered

- **Binary items, to mirror `supported | refuted`.** Rejected, and the intuition points the
  other way. ADR-0010's criteria are binary because each carries a written `pass_condition`;
  a holistic item has no threshold, so a yes/no forces the rater to invent one silently —
  the *"opaque `ScoringPolicy`"* ADR-0010 refused, relocated inside the expert and no longer
  auditable. And a human answering in the instrument's own shape stops being independent
  evidence: what would be measured is the reliability of a shared procedure, which cannot
  detect that the procedure asks the wrong question — the failure `backend/README.md` already
  names (*"a criterion can be perfectly stable and stably wrong"*). ADR-0015 §1 exempts layer 1
  from ADR-0010 for this reason.
- **Keeping five dimension items and improving only their anchors** (the literal reading of
  clause 3's "light review"). Rejected: it fixes the ceiling and leaves clause 4 unavailable.
- **One item per quality, all nineteen.** Rejected on rater budget; twelve is what four courses
  per SME affords without the primary measurement degrading.
- **Seven points instead of five.** Rejected: no gain at this number of contents, and it would
  move the scale ADR-0015 §3 names and the `CHECK` that encodes it, for nothing.
- **Hiding an undeclared item and recording `not_applicable`.** Rejected — it is the one
  mapping that manufactures disagreement, since the automated side derives a penalising
  outcome from the same fact (clause 7).
- **Showing every item always, with the bottom anchor absorbing the absence.** The closest
  call, and rejected on the same argument that governs the automated path: asking a rater to
  judge how well a course delivers what it never promised is asking them to judge the
  unjudgeable, and the answer they give would be a guess where the machine has a fact.
- **A second `ContentVersion` for the processed course**, joined to the draft by logical
  content and `edit_provenance = human_edited`. Rejected for now — it is the rigorous shape
  and it buys nothing until the processed deliverable is an evaluand in its own right, while
  costing a join on every calibration read.

## References

Amends ADR-0015 §3 (shape of the layer-1 reference instrument); ADR-0015 §§1, 4, 5 stand as
written. Depends on ADR-0026 (one quality per claim) for the exactness of the join, and on
ADR-0021 / ADR-0023 §2 for what an absence must do to a denominator. Clause 6 reads ADR-0028
(`consumableUrl` declares deployment) and ADR-0046 (a proposal is evidence of alignment).
Clause 7 mirrors the mechanical derivation of `12-define-qa.md` (Pedagogical Evaluation,
invariant 2) and ports ADR-0021's `derived` column to the human path. Achieve OER's holistic
per-construct elicitation remains the pattern for layer 1, as in ADR-0015.
