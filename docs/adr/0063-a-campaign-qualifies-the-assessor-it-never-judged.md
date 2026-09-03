# ADR-0063 — A campaign qualifies the assessor over courses it never judged

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Reporting · Pedagogical Evaluation ·
Calibration

## Context

ADR-0015 §4 asked for **validity coefficients per claim** — each claim correlated with the human
score of *its* quality — and ADR-0052 §1 made that join exact by putting the reference
instrument's item and the claim's quality on the same id. ADR-0062 then named the column
accordingly. Everything the comparison needs is in the database and nothing computes it:
`STATUS.md` has listed it as *not built on purpose* since, because it "crosses a campaign with a
study".

The crossing is the whole feature, and the question it has to answer is not *what did the panel
think of these forty courses* — a campaign already reports that (ADR-0060). It is:

> **What may we conclude, from forty judged courses, about the courses nobody will ever judge?**

The answer this decision rests on is that the transferable thing is not a fact about a course. It
is a fact about the **pair `(assessor version, claim)`**: how much that claim, executed by that
assessor, moves with expert judgment. That pair is what a study pins over *any* dataset, so what
is measured on the campaign's courses is a property of the instrument that travels with it.

An expensive campaign is therefore amortised over every future version of the assessor:
recalibrating a new one costs a run over the same forty courses, not another panel.

## Decision

**A campaign qualifies a claim of an assessor version; the result is a read, it names the
campaign it came from, and it never becomes a verdict about a course.**

### 1. The grain is `(assessor version, claim)`, and the join is the quality

A claim asserts about exactly one quality (ADR-0026); the reference instrument's item **is** its
quality (ADR-0052 §1, ADR-0062). So `item_scores.quality_id` meets `instrument_claims.quality_ids`
with no mapping table, and the evaluand is one `contentId` on both sides (ADR-0052 §6).

**The grain buys discrimination between claims, not attribution to one.** Where a quality carries
several claims they are all compared against the same human column, so it is answerable whether
*this* claim's verdict moves with expert judgment — each claim partitions the courses
differently, and the partition is its own — and it is *not* answerable which claim explains a
weak quality. Where several claims share a quality the reading is comparative: divergence is the
finding, and two claims that separate identically have shown they are redundant.

### 2. The two sides are made comparable by a declared cut, and the middle is counted

The automated side is binary by construction (ADR-0010). The human side is a 1–5 agreement scale
(ADR-0052 §3). The mean of a course's raters is read as **accept at ≥ 4, reject at ≤ 2**, and what
falls between is a **grey zone**: outside the 2×2 and **reported as a count**.

The grey zone is reported rather than dropped because it is not noise about the assessor. A claim
with half its courses there is telling us **the human item does not separate** — a fact about the
form, and one that would be invisible if the middle were silently discarded. Abstentions
(ADR-0052 §4) and derived values (ADR-0053) stay out of both: nobody judged them.

The cut is a **declared decision, not a finding**. Binarising after collection is a different act
from asking a human a yes/no question, which ADR-0052 rejected for relocating an unwritten
threshold inside the expert.

### 3. What is reported per claim, and why not a single agreement figure

Sensitivity — *of the courses experts accepted, on how many did the assessor say `supported`* —
and specificity, its mirror. **Always with their counts** (`9 of 11`), never a bare percentage: a
proportion without its denominator is an assertion without a size.

A single "agreed 82 % of the time" is refused, and the reason is structural rather than
stylistic: an assessor that approves everything scores high on it while detecting nothing, and it
scores higher the rarer the defect. The two numbers are class-conditional — computed *inside*
each group of the reference truth — which is also why they survive a change in the mix of good
and bad courses, and therefore why any of this transfers at all.

`sensitivity + specificity − 1` is reported beside them. It grades the claim and it is the
factor a population correction would divide by, so one quantity does both jobs; at or below zero
the claim does not beat chance and nothing about it is published.

### 4. The ceiling is the panel's agreement with itself, measured the same way

If two experts do not agree with each other, there is no human answer for the assessor to match,
so their agreement is the maximum it can reach. Every row carries it.

**And the comparison is like with like.** The acceptance rule of automated scoring (Williamson, Xi
& Breyer 2012) is an absolute threshold plus a relative one — *the judge may be worse than a
second human, but not more than 0.10 worse* — and the relative half only means something if both
halves are the same statistic. So:

- the **ceiling** is the proportion of courses where the two raters' **binarised** verdicts
  agree, pooled within courses the way ADR-0060 §5 pools them;
- the **judge–human agreement** is the same proportion over the same 2×2;
- **degradation** is their difference, and the gate is `≤ 0.10`;
- **Cohen's κ is reported separately**, as the chance-corrected headline, against its own
  absolute threshold.

Reading κ against a percentage would have subtracted two different units. The unit mismatch is
recorded here because the design note carried it and the code would have inherited it silently.

### 5. `status` is the only field that opines, and its thresholds are a value

`tracks` · `weak` · `unvalidated`, each with its reason. Initially: `tracks` when κ ≥ 0.6, n ≥ 15
and degradation ≤ 0.10; `unvalidated` when n < 10, when a row of the 2×2 is empty, or when the
ceiling is at the floor; `weak` otherwise.

**Those numbers are reasonable, not measured**, and they are declared as constants rather than
buried in the logic precisely so the first campaign can move them without touching a rule. A
claim the assessor never refutes has an empty row and no specificity to measure — no number of
raters fixes that, because the claim never distinguishes anything.

### 6. Every claim of the pinned version is listed, including the ones with no human item

Seven of `course-drafts-qa-v9`'s twenty-one claims assert about a quality the reference instrument
does not elicit. They appear as `unvalidated`, reason *no reference item*. A reading that showed
only the claims with data could not be told apart from an instrument that never had the others —
the coverage lie ADR-0011 §3 refuses, and here it would hide a third of them.

### 7. The campaign is an explicit parameter, and two campaigns are never averaged

The read takes `(campaign, assessor, instrument version)` explicitly. Nothing is inferred: the
result is a property of *that* pair, and a defaulted coordinate would let one URL mean different
things over time — the objection ADR-0056 raised about pinning in general.

**Naming the campaign dissolves the reconciliation problem instead of solving it.** Two campaigns
that disagree are read by asking for each in turn, and the disagreement is the finding: either the
population moved or one of them was noisy. **Averaging them is forbidden**, because it converts
exactly that finding into a middling number — and detecting drift is why a second campaign is run
at all. It also makes the incomparable case unrepresentable: the campaign fixes the human side
entirely, so naming it *is* naming the version of the form, and two versions cannot be mixed.

On a reading surface the campaign is **optional**, and with none chosen there is **no badge** —
which is not `unvalidated`. *Nobody measured this* and *we measured it and it does not conclude*
are different facts, and ADR-0011 §3 is the reason to keep them apart.

### 8. It is a read, it persists nothing, and it stays out of the frozen record

Composed on demand through query ports (ADR-0006), like the fitness projection (ADR-0023 §10).
There is nothing to store that is not recomputable from what exists, and storing it would oblige
us to build invalidation — the cost this shape exists to avoid. It is persisted the day somebody
needs to *pin* it, and not before.

It does **not** enter `study_reports.report` (ADR-0041): validity can change when another campaign
lands, and a frozen document may not hold a value that moves. It does not enter the fitness
projection either — a fitness that shifted whenever a campaign ran would break the
cross-generation comparability that is the only thing the GA needs.

### 9. Nothing here corrects a course

What transfers is a group expectation — *in the courses where the assessor said `refuted`, experts
scored 2.4 on average* — and a group average is nobody's score. Correcting an individual course
would need a model that forty courses cannot support, and it would look exactly like a grade.
The population-rate correction that the same two numbers make possible (Rogan & Gladen 1978) is
deliberately **not built here**: it needs a randomly sampled campaign and a consumer that asks
for it.

### 10. The surface is called *validity*; the domain still says *Calibration*

`Calibration` and `CalibrationProfile` remain the GLOSSARY's words for this concept, with the
grain ADR-0062 corrected. But `calibration` is already the console for **tuning an instrument** —
the dry run, the traces, `drafts_hybrid/calibration.py`, `RUNBOOK-calibrating.md` — and the study
report deep-links into it. Reusing the word on a route would collide with a live contract.

*Validity* is not a workaround: it is what ADR-0015 §4 calls this ("validity coefficients"), and
it is the right word — the tuning console measures whether an instrument is **reliable**, this
measures whether it is **valid**, and a thing can be perfectly reliable and stably wrong.

## Consequences

- (+) `STATUS.md` loses its oldest deliberate gap, and ADR-0015 §4 becomes executable rather than
  aspirational.
- (+) One expensive campaign now qualifies **every** later assessor version at the cost of a run
  — which is the promise ADR-0015 made and never had a mechanism for.
- (+) No table, no event, no module. `SourceCalibrated` stays reserved and unpublished.
- (−) **Forty courses buy a coarse diagnosis and nothing finer.** With the groups a claim splits
  into, the interval on a proportion is wide enough to separate *tracks* from *weak* and not
  0.55 from 0.70. The design promises three categories on purpose.
- (−) **Random sampling was chosen for the first campaign** (time, and the need to include both
  package formats), so claims the assessor rarely refutes will come back `unvalidated` with a
  nearly empty row. That is the expected cost of the choice, not a defect.
- (−) The thresholds of clause 5 are asserted, not measured, and the first campaign is what
  settles them. Until then a `status` is an opinion with a declared rule behind it.
- (−) Reading validity for a claim requires that somebody ran the assessor over the campaign's
  courses. Nothing automates that: it is a study over the dataset version the campaign used.

## Alternatives considered

- **Correlating the 1–5 with the verdict instead of binarising.** Rejected: the automated side is
  binary (ADR-0010) and no correlation makes it finer, while the two proportions the 2×2 yields
  are what a population correction would later need — one computation serving both.
- **Reporting a single agreement percentage.** Rejected by clause 3: it rewards guessing the
  frequent answer, and it hides which side the judge got right.
- **Averaging two campaigns**, or letting the most recent silently win. Rejected by clause 7.
- **Persisting a `CalibrationProfile`.** Rejected by clause 8, and revisited when somebody needs
  to pin one.
- **Putting the badge on every surface that shows a verdict.** Rejected as scope: the study report
  is where a verdict changes a decision, and the rest can follow if it earns its way.
- **Calling the route `calibration`** and renaming the tuning console. Rejected: it drags a
  rename of a live page, its tests, its runbook and a cross-screen deep link through a feature PR,
  and *validity* is the more accurate word anyway (clause 10).

## References

Realizes ADR-0015 §4 (validity coefficients per claim) and §5 (the human ceiling reported
alongside) · depends on ADR-0026 and ADR-0052 §1 for the exactness of the join, and on ADR-0062
for its column · follows ADR-0006 for composition on read and ADR-0023 §10 for persisting nothing
· honours ADR-0060 §1 (one definition of a campaign's evaluations, now shared rather than
duplicated) and §8 (which excluded these coefficients from the campaign report, and is why this
is its own resource) · ADR-0011 §3 for why an unmeasured claim is listed rather than hidden ·
ADR-0041 for why it stays out of the frozen study report · Williamson, Xi & Breyer (2012) for the
absolute-plus-relative acceptance rule of clause 4 · Rogan & Gladen (1978) for the correction
clause 9 defers · the full design and its ten decisions in `notes/` (working, not maintained).
