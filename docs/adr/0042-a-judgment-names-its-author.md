# ADR-0042 — A judgment names its author, and a study's result is a triple

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies · Evaluation ·
Identity

## Context

`quality_judgments` has no `assessor_id`. The fact is not lost — `evaluation_id` is NOT NULL
with a unique FK to `evaluations`, whose `assessor_id` is NOT NULL too — but it reached no
reader, and four things followed from that:

1. **`latest_judgments` takes the most recent judgment per content, whoever produced it**
   (`report.py`). Its key is the content alone.
2. **`compose_report` emits the assessor nowhere.** `judgmentIdsUsed` freezes *which*
   judgments the document reflects and never *whose* — and a uuid minted in one store means
   nothing in another, so even reconstructing it later depends on that database still
   existing.
3. **The console's durable count is assessor-blind while the batch's skip is not.**
   `read_study_evaluations` counts judgments per instrument version; `batch_runs.prepare`
   skips per `(assessor, content, instrument)`. The two answer different questions and were
   presented as one number.
4. **The fitness projection publishes `ratifiedAssessors` — who MAY judge, not who did.** Its
   own note says values computed under different assessor coverage are not comparable, and it
   had no way to detect that it was looking at a mixture.

So: evaluate half a study with `drafts-hybrid:10`, bump to `:11` to repair three courses,
publish — and the immutable record silently pools two judges, while the optimization signal
the genetic-algorithm experiment reads averages across them.

**None of this was decided.** ADR-0006 §3 collapsed repetitions per `(assessor, content,
rubricVersion)`, **with the assessor in the key**, because several humans judged one course.
Slice 2 reduced that key to the content alone, at a moment when exactly one automated
assessor could exist per lineage; ADR-0034 recorded the working rule — *within one study,
evaluate each content with one assessor* — and nothing enforced it. Every version bump makes
a second assessor (ADR-0016: any change to code, model, prompt or threshold is another
artifact), so the rule became breakable the first time `drafts-hybrid` was bumped, and stayed
a discipline held in a person's memory. ADR-0017 already recorded what that is worth:
discipline depending on institutional memory is not discipline.

The GLOSSARY had asked for the missing half all along: a `QualityJudgment` is *"a per-criterion
profile + coverage + **provenance (`assessor` …)**"*. This does not add a concept. It realizes
one the model always declared.

## Decision

**A judgment names its author everywhere it is read, and a study's result is defined by a
triple: its dataset, its instrument version and its assessor.**

### The author travels

1. **Provenance is read, never re-stored.** `QualityJudgmentDTO` gains `assessor_id`, resolved
   through `evaluations` — the coordinate already exists with a unique FK, and a second copy
   of it on the judgment row could drift from the first. `DeriveJudgment` and `JudgmentRecord`
   are untouched, which is what makes this migration-free for every judgment ever derived.

2. **The id comes from Evaluation; the label comes from Identity.** Evaluation joins only
   `evaluations`, a table of its own. What an assessor is *called* — `name:version` from
   `source_config`, ADR-0016's identity rule — belongs to Identity, and the gateway that
   already crosses module boundaries asks Identity's batched `list_assessors` for it. Reading
   `assessors` from Evaluation's SQL would re-encode that rule in a second module with nothing
   to keep the copies in step.

3. **Both forms are published.** The id names the row; `name:version` is the only form that
   still means something once the store that minted the row is gone. This is ADR-0039 §4's
   argument for publishing a brief's hash beside its id, applied to the judge.

4. **The report names the author per course, names the distinct authors in its header, and
   raises a `mixedAssessors` caveat when there is more than one.** Per course as well as in
   the header because the grain of the mixture is the course. The caveat key is always
   present, empty below two authors, like every other kind (12-define invariant 4).

5. **`SCHEMA_VERSION` moves to 2**, and the contrast with ADR-0041 §8 is the rule rather than
   an inconsistency: that decision left the version alone because `compose_report`'s output
   was byte-identical. Here what publishing writes changed. The bump is a *signal* and not a
   guard — nothing branches on it — so the field-level protection is that every new key is
   **optional** in the frontend types and read defensively. A report frozen at version 1 is
   the record it is, and is never annotated with a reconstruction.

6. **The fitness projection publishes `assessorsUsed` beside `ratifiedAssessors`**, and the
   note says which is which. Ratification is instrument-scoped and permissive; participation
   is study-scoped and is what the equal-coverage rule of ADR-0023 §7 was actually about.

7. **The durable count is split per assessor.** The total stays — *how much of this study has
   been judged at all* is a real question — and the split answers the one the start dialog is
   asking: how much would this assessor skip. The console's "up to N" was an honest patch for
   a number that could not be computed; it can be now.

### The study pins its assessor

8. **A study pins one assessor, once, before opening, and `open()` refuses without it** —
   exactly the shape of the instrument pin (12-define invariant 1, which this amends by
   adding a second pin). `prepared` derives from both pins plus a composed dataset. The pin is
   refused unless that assessor has ratified the study's pinned instrument version, so the
   instrument is pinned first.

9. **Every read of a study filters judgments by its pinned assessor**, in SQL rather than in
   Python: a judgment by anyone else is not part of that study's result and its evidence
   should not be transferred to look at. A study with **no** pin — one that predates this —
   reads exactly as it did before, and clause 4's caveat is what tells its reader why.

10. **The batch takes the assessor from the study.** `evaluate-study --assessor` and the HTTP
    request field become optional and are **refused when they disagree with the pin** rather
    than ignored: scripts that already pass it keep working, and a mismatch is stated instead
    of silently resolved. The single-content `evaluate` stays study-agnostic — it does not know
    which studies a content belongs to, and under clause 9 a stray judgment simply does not
    count, which is the property the pin buys.

11. **Studies that predate the pin are backfilled where the answer is unambiguous** — exactly
    one distinct author across their current judgments — and left unpinned where it is not.
    An unpinned study is not repairable after opening: the pin follows the same
    before-open rule as the instrument. A study already mixed is a study whose result mixes
    judges, and clause 4 makes that readable; pretending otherwise by letting somebody choose
    one of the two afterwards would rewrite what happened.

## Consequences

- (+) The frozen report can answer *who judged this* without the database that produced it.
- (−) **Repairing a study with a bumped assessor costs a full re-evaluation of its dataset**
  (~16 LLM calls per course today), or a new study over the same contents. This is the price
  of clause 8 and it was accepted deliberately: a result that pools two judges is not a
  result, and the alternative — keeping the mixture legal and merely visible — leaves the
  reader to do arithmetic the system refused to do.
- (−) The order of setup changes: an assessor must be **ratified before a study opens**, where
  before a study could open and wait. Readiness reports the gap, so it informs before it
  blocks, but `open()` does block, which readiness itself never does.
- (−) Several assessors over one dataset become impossible for now — the deliberation
  `[future]` and the inert `unresolvedDisagreements` caveat both assume it. Reopening that is
  "the pin becomes a list", a widening rather than a reversal, and the caveat stays in place
  meanwhile.
- (−) `EvaluationGateway` now crosses to two modules instead of one. That is what a gateway is
  for, and the alternative (clause 2's rejected join) costs more.
- (−) One extra batched query per report/preview/fitness composition, for the labels.
- Reports published before this carry no author. They are frozen and are read as the records
  they are — the same treatment ADR-0024 gave the `unknownExclusions` wording it superseded.

## Alternatives considered

- **Store `assessor_id` on `quality_judgments`** → rejected: it duplicates a fact the schema
  already enforces through a unique FK, needs a migration and a backfill, and opens a
  denormalization that can drift. The join recovers it losslessly for every row that exists.
- **Join `assessors` from Evaluation's own SQL** → rejected: `assessors` belongs to Identity,
  and `source_config->>'name'` is ADR-0016's identity rule. It would be the repo's first
  cross-module table read, and the architecture test checks imports, not SQL — so it would
  pass green, which is exactly why it had to be decided rather than defaulted into.
- **Name the author and stop there — keep "most recent wins", caveat the mixture** → rejected
  as the destination, kept as the first half. It is honest and it does not close doors, but it
  leaves a legitimate way to produce a study whose every distribution pools two judges, and
  leaves the fitness value the GA optimizes against defined by whoever ran the last batch.
- **Refuse to publish a study whose judgments come from more than one assessor** → rejected:
  publishing with caveats is legitimate and visible (12-define invariant 4), and a refusal
  would strand an already-mixed study with no exit but re-evaluating everything.
- **Let an unpinned study be repaired one-way after opening**, the way ADR-0024 lets an
  `unknown` generator be attributed later → rejected. The two look alike and are not: a
  generator attribution is a *discovery about the past* that fills a declared void, while
  choosing one of two judges after both have judged *decides which half of the evidence to
  disown*. Clause 11.
- **Pin a set of assessors rather than one** → deferred, not rejected. It is the shape the
  deliberation `[future]` will need, and building it now would be a mechanism with no
  consumer and no rule for combining what two judges say.
- **Make the study's assessor re-pinnable while open, invalidating what the old one judged**
  → rejected: it is clause 8 with a shortcut, and the shortcut hides the cost. Re-evaluating
  the dataset is the same work either way, and doing it under a new study keeps both results.

## References

ADR-0006 §3 (repetitions collapse per `(assessor, content, rubricVersion)` — the key this
restores) · ADR-0016 (an automated assessor's identity is `(name, version)` in
`source_config`; any change is another artifact — which is what makes two assessors ordinary)
· ADR-0019 (ratification: why two assessors over one instrument version are possible at all,
and the act clause 8 checks) · ADR-0034 §"one artifact per study" (the working rule this
enforces; judgments do not combine across assessors) · ADR-0023 §7 (equal coverage: the
comparability rule clause 6 makes checkable) · ADR-0039 §4 (id versus portable identity — the
argument for clause 3) · ADR-0041 §6 and §8 (a published study is read through the judgments
its report recorded; and the `SCHEMA_VERSION` test clause 5 applies in the other direction) ·
ADR-0024 (the one-way repair clause 11 declines to copy, and the frozen-wording precedent) ·
ADR-0017 (discipline depending on institutional memory is not discipline) · 12-define
invariant 1 (the instrument pinned once before opening — amended here by a second pin) and
invariant 4 (caveats always present) · GLOSSARY (`QualityJudgment`, whose *provenance* this
realizes; `EvaluationStudy`; `Fitness`).
