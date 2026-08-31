# ADR-0060 — A campaign's result is read inside the campaign that produced it

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Reporting ·
Evaluation Orchestration

## Context

ADR-0006 gave Reporting its shape — compose the other modules through their query ports,
aggregate in Python, a per-criterion average across assessors plus dispersion — and it did so
when there was one campaign. The read models it produced take no campaign at all.
`build_scores_report` begins at `list_content_snapshots()`, the whole registry, and averages
every evaluation it finds for each content.

Four different things are pooled there, and only the first is visible to anybody reading the
screen.

**Campaigns.** ADR-0002 made the campaign the unit that fixes what a number means: scope,
quorum and instrument version, all fixed when it opens. ADR-0005 then made the evaluation
deliberately campaign-agnostic — the link to a campaign is the **assignment**, so one
evaluation may satisfy several campaigns. Aggregating by `contentId` alone therefore pools the
assessors of one round with the assessors of another, and nothing says which round a number
came from.

**The registry.** A course no campaign has ever put in front of anybody is a card in the
report, with zero evaluators, beside the courses that were judged.

**Instrument versions.** `collapse_latest_per_assessor` keys on
`(assessor, content, instrumentVersion)` and is right about it; `scores_by_criterion`, one
call later, drops the version and pools every evaluation into the same criterion bucket.
Between v1 and v2 the ids mostly differ and the defect hides. ADR-0052 made the item's
`criterionId` **be** the `qualityId` — so from v2 to v3 the ids collide by construction, and
two wordings of the same statement will average together in silence. ADR-0056 exists to make
the pinned version a choice somebody makes and can see; nothing downstream reads the pin.

**Human and automated.** ADR-0034's assessors write into `evaluations` as well, with their
verdicts in `criterion_outcomes` and nothing in `criterion_scores`. Those rows reach the
report carrying no scores — so the averages survive — and are counted: on any course a study
has measured, `evaluatorCount` includes the model's runs.

Underneath the pooling there is a second defect, and it is not about scope. The report is
aggregated on an axis that cannot answer the question the panel exists for. ADR-0052 §5 chose
its twelve items *"where validity is at risk"*, and what tells the two failure modes apart is
whether two experts reading the same course answer an item the same way. The first reference
campaign is 40 courses with two assessors each: at `content × item` every cell holds one pair,
at `item × campaign` it holds forty. Only the first is on screen. What ADR-0052 §1 kept the
`dimension` column for — *"a grouping for reports"* — has no reader at all, and the individual
answers the endpoint already returns, each with its assessor's comment, are fetched by the
console on every request and rendered nowhere.

## Decision

**A campaign's result is read inside the campaign that produced it, at the grain of the
item.**

### 1. Membership is the assignment, not the content

An evaluation belongs to a campaign when a **non-cancelled assignment**
`(campaign, content, assessor)` exists and the evaluation's `instrumentVersion` equals the
campaign's. That is not a new rule: it is the completion policy's, the one that decides which
campaigns a submission advances. The report counts exactly what the quorum counts, and a
second definition of *this campaign's evaluations* — which would drift — never exists.

Two consequences follow from it, and both are wanted:

- **The report filters; it does not partition.** One evaluation may appear in two campaigns'
  reports, because ADR-0005 made that legal on purpose and ADR-0002's quorum already relies on
  it. What is forbidden is the pooling, not the sharing: two campaigns each read that
  evaluation among *their own* assessors, and neither averages it with the other's.
- **An automated evaluation appears in no campaign report**, because no assignment ever names
  one. The inflated `evaluatorCount` stops being a case to handle and becomes a case that
  cannot arise.

### 2. The primary axis is the item over the campaign, not the course

The course-by-course profile stays, second. First is the item read across the whole campaign,
because that is where the campaign's own question has an answer and where the arithmetic has
enough observations to give one.

### 3. The items come from the pinned instrument, not from the answers

Every item of the pinned version is listed, in its own `order` and under its own `dimension`,
including one nobody answered. A report showing only the items with data cannot be told apart
from a report of an instrument that never asked them — the coverage lie ADR-0011 §3 refuses in
the other direction. The grouping ADR-0052 §1 reserved gets its first reader here, and stays
what that clause made it: a place where qualities are **read** together, never where they are
elicited or summed.

### 4. Three silences, and they are not one

A cell with no number holds one of three different facts, and each leads somewhere else:

- **not asked** — the course declares nothing the item could be about, so the value was
  derived and nobody was put in front of it (ADR-0053). It is the generator's omission.
- **abstained** — the item was asked and the expert answered *I could not judge this*
  (ADR-0052 §4). It is a fact about the evidence, or about the item.
- **not submitted yet** — nobody has looked. It is a fact about the campaign's progress.

They are rendered as three different things. Today all three print as a dash, and a dash that
means *the generator forgot* reads identically to one that means *we are not finished*.

### 5. Agreement is pooled over the courses, at ADR-0006's grain of metric

Pairs are formed **within one course and one item** — the only place two answers are about the
same thing — and pooled across the courses of the campaign. Reported: the pair count, the mean
absolute difference, the percentage of exact agreement, and the percentage within one point.

ADR-0006 §2 fixed this family of metric ("standard deviation + mean absolute pairwise
difference + % exact agreement") and deferred Krippendorff's α to `[future]`; that deferral
stands. **Percentage within one point is added**, because ADR-0052 §3 replaced a numeric scale
with agreement to a statement: on an ordinal Likert, *agree* beside *strongly agree* is not
the disagreement that exact agreement alone reports it to be, and the campaign's ceiling
(ADR-0015 §5) would be read as far lower than it is.

### 6. The cross-campaign scores report is retired; the cross-campaign progress report is not

The two halves of `/admin/reports` answer questions of different kinds, and only one of them
survives leaving a campaign.

*Who is overloaded, who abandoned, who has not opened anything* is a question about **people**,
and 25 experts across several rounds is exactly when it needs asking across campaigns.
`GET /admin/progress` keeps its scope.

*What a course scored* is a question about a **measurement**, and it has no answer outside the
campaign that fixed the instrument, the scope and the panel. `GET /admin/reports/scores` is
therefore deleted rather than given a filter: a filtered version would be a second way to ask
the same question, and the one thing the defect above proves is that a report whose scope is
optional will be read with the scope off.

Nothing is lost. A human evaluation can only be submitted against an assignment, and an
assignment belongs to a campaign — so **every** human evaluation the system holds is already
inside at least one campaign report.

### 7. The campaign report is composed on read, not frozen

ADR-0041 built a frozen document for a study, because a study's result is signed off and
becomes a record. A campaign's record is not its report: it is the **golden reference**, which
its own policy establishes from coverage and which already exists. So there is no sign-off
here, no immutable body and no preview/frozen pair — the report is recomposed from the
assignments and evaluations that exist at the moment it is read, and a band at the top says
whether the campaign is still open, so that a screenshot taken at 40% cannot be mistaken for a
result.

### 8. What it does not carry

**The validity coefficients of ADR-0015 §4.** They correlate a claim with the human score of
its quality across a set, which crosses a campaign with a study; nothing in the system computes
a correlation yet, and half of one printed inside a campaign report would be read as the whole.
The report says whether the campaign is usable as a reference and stops there.

**Assessor severity.** Deliberately unmeasured for the first campaign, and naming it here
keeps that a known absence rather than an oversight.

## Consequences

- (+) **The `evaluatorCount` defect disappears as a consequence of clause 1**, not as a patch —
  there is no filter on assessor kind anywhere, because the membership rule never admits one.
- (+) **ADR-0052 §5 becomes readable.** *Which items are answerable* is a column, sorted worst
  first, over enough pairs to mean something.
- (+) The individual answers and comments the endpoint has always returned finally have a
  reader, which is the cheapest thing on this list and the one an expert panel notices.
- (−) **A course in two campaigns is read twice, and the two readings may differ.** That was
  always true; it is now visible, and clause 1 makes it legible instead of averaging the
  difference away.
- (−) **One request carries the whole campaign**, per-assessor detail included — around a
  thousand score rows for the first campaign. At the volume ADR-0006 §1 sized for, the cost is
  nil, and one payload keeps the page honest about being one reading of one campaign.
- (−) **Reporting composes a fifth module.** It already reaches Evaluand Registry, Evaluation,
  Identity and Orchestration; the pinned instrument's items and their dimensions come from
  Evaluation Design. Through `public.py`, as the other four do.
- (−) `GET /admin/campaigns/{id}/progress` was an N+1 over the scope, harmless with a demo
  campaign and not with forty courses. The report reads it rather than recomputing the quorum,
  so `is_complete_with` stays the only writer of that rule — and the query is made to count in
  one pass.

## Alternatives considered

- **Filter the existing report by an optional `campaign_id`.** Keeps one endpoint and one
  screen, and keeps the defect one query parameter away — with the unfiltered call still the
  default and still wrong. It also leaves the axis untouched, which is the half of the problem
  that scoping does not fix.
- **Partition evaluations across campaigns, so each belongs to exactly one.** Would need
  either a `campaign_id` on `evaluations` or a rule picking a winner, and both contradict
  ADR-0005's reason for leaving it out: one submission legitimately satisfies several
  campaigns, and the quorum depends on it.
- **Freeze the campaign report at close, like a study's.** Buys immutability nothing consumes:
  the artefact a campaign hands downstream is the golden reference, and a second frozen record
  beside it would be a document with no reader and a second answer to *what did this campaign
  find*.
- **Keep the course as the primary axis and add agreement inside each course.** It is the
  arrangement that has one pair per cell. Every number would be a comparison of two people on
  one item, and the item's behaviour across the campaign — the thing being validated — would
  have to be assembled by eye over forty cards.

## References

ADR-0006 (composition via query ports, aggregation in Python, the dispersion family and the
α deferral this stays inside) · ADR-0002 (what opening a campaign fixes; the quorum this
counts with) · ADR-0005 (the evaluation is campaign-agnostic; a repetition is a correction) ·
ADR-0011 (no aggregate across criteria; the coverage lie §3 refuses) · ADR-0015 (the human
reference in two layers: §4's validity coefficients, deferred here; §5's human–human ceiling) ·
ADR-0041 (the frozen report is the record, not the reading surface — the pattern this
deliberately does not repeat) · ADR-0052 (one item per quality, the Likert response, the
abstention off the scale, `dimension` as a grouping for reports) · ADR-0053 (an undeclared
datum is not asked of a human) · ADR-0056 (the campaign pins its reference instrument) ·
ADR-0059 (a course carries the name its package declares).
