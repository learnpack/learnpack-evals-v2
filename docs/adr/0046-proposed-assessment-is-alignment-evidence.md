# ADR-0046 — What a draft proposes to assess with is evidence of alignment, and travels marked

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Content Profiling · Evaluation
Design

## Context

A LearnpackV2 package is a generator run's output **before** the teacher's processing step. For
exercises the format does not emit the artifact but a **proposal**: a
` ```code_challenge_proposal ` block inside the lesson body saying what the learner should be
asked to build, which the teacher's step turns into exercise files. For images it does the same
with an illustration prompt.

The extraction adapter excludes those proposals, deliberately and in writing
(`learnpack_v2.py`, its docstring: *"`code_challenge_proposal` … are not assessment items"*,
and *"Proposals get their own id when an instrument mints one; until then they are not evidence
for anything"*). So `lesson_assessment_items` collects only what ships ready for the learner —
`question` and `fill_in_the_blank` fences and indented quizzes. **No ADR ever ratified that
decision**; it lived in a docstring and in the headers of the `course-drafts-qa` lineage.

Counted over the five drafts on hand, with the adapter's own counting on both sides, that
leaves between 40 % and 82 % of the assessment surface invisible:

| Draft | delivered items | proposed exercises | invisible |
|---|---|---|---|
| CSS | 12 | 8 | 40 % |
| HTML | 5 | 5 | 50 % |
| Command line | 3 | 14 | 82 % |
| Git | 3 | 10 | 77 % |
| GitHub | 3 | 14 | 82 % |

The three drafts at the bottom deliver a single question block each: they are one component
away from offering nothing a learner can answer as it stands, and everything a learner would
actually do.

And the part that turns a proportion into a defect: **the five objectives that repeated judging
reported as measured by nothing are covered by proposals**, several of them near-verbatim
against the objective's own declared verification — an objective verified by *"writes a complete
.html file that renders a heading, a paragraph, an image, and a link, correctly nested"* sitting
next to a proposal asking for exactly that; a CSS objective verified by *"write a media query
that stacks the columns vertically when the viewport is below 600px"* next to a proposal asking
for a media query that stacks the two flex columns below 600px.

Two consequences follow, and neither is a finding about a generator:

- `cr-every-objective-has-an-assessment-item` failed on all three judged drafts as an **artifact
  of the extraction**.
- `cr-assessment-matches-the-declared-verification` failed systematically with one reason —
  *the declared verification asks for production and the items ask for recognition* — and that
  reason does not merely weaken when proposals are read: **it reverses**, because the proposals
  are the production.

The adapter's own docstring contains the argument against itself. It refuses to declare
`lesson_activities` with an empty list because *"an empty list derives a fail for a defect that
does not exist"*. A **partial** list produces exactly that fail, with the aggravation that the
partiality is invisible to the criterion reading it.

## Decision

**What a draft proposes to be assessed on is evidence for the alignment claims, and it is
extracted under one id that carries the whole assessment surface with every entry marked
delivered or proposed.**

1. **A proposal is a commitment to assess.** The question the alignment criteria ask is whether
   the draft commits to measuring what it declared, and at this stage the commitment IS the
   proposal. Reading only what ships answers a different question — whether the teacher's step
   has already happened.

2. **One id, `assessment_offerings`, minted by `course-drafts-qa` v7** (ADR-0014:
   similar-but-different → a new id, never a redefinition of an existing one). It carries every
   task the content offers to assess with — `lessonSlug`, `lessonId`, `status`, `kind`,
   `prompt` — where `status` is `delivered` or `proposed`, reported by the adapter and never
   inferred.

3. **`lesson_assessment_items` is untouched and stands beside it.** It remains what it always
   was, the delivered half alone, consumed by the `learnpack-course-qa` lineage; the new id
   does not replace it, it covers it. Two ids over overlapping data, consumed by different
   criteria, is the shape ADR-0014 already produced once for `learning_objectives` and
   `declared_objectives`, and for the same reason.

4. **One list rather than two, because a criterion is silent when any datum it requires is
   absent.** Splitting delivered and proposed into two required ids would leave a draft that
   offers only one of the two forms unjudged — and three of the five drafts on hand are a
   single question block away from being all-proposals. The cost of the choice is stated in
   §Consequences and is permanent.

5. **The three criteria of `course-drafts-qa` v7 that read assessment require the new id**, and
   each one **says in its own words which of the two it counts**. That sentence is not a
   courtesy: it is what replaces the guarantee two ids would have given structurally.

6. **The five criteria that require materialized exercises stay out, with their three claims.**
   How an exercise's scaffolding fades and in what order practice arrives cannot be answered
   from a proposal. That is ADR-0032's argument and it is undisturbed: what changes here is
   constructive alignment, where the question is not *is this practice good?* but *does the
   draft commit to assessing what it declared?*

7. **This is a version of the lineage, not a fork.** By ADR-0032 §3 the test is whether the same
   thing is being asserted: `cl-assessment-measures-the-declared-objectives` asks what it always
   asked. Its statement widens from *the assessment items the draft carries* to *the assessment
   the draft offers — delivered or proposed*; the evidence admitted widens, the assertion does
   not move.

## Consequences

- **The distinction between delivered and proposed stops being structural and becomes
  textual.** With two ids, a criterion about shipped assessment could only be written by
  requiring the shipped id; with one, a criterion whose pass condition forgets to say which it
  counts will silently count proposals as delivered work. The mitigation is discipline plus two
  places that make it visible: every pass condition here names both, and the assessor shows the
  judge each entry marked (`proposed exercise` / `delivered item`), so a verdict that conflated
  them is legible in its own quote.
- **A profile carries the delivered items twice**, once under each id. Accepted: supply is
  cheap, and collapsing the two would either redefine a global id per format or delete
  information the other lineage consumes.
- **Two criteria stop failing for the wrong reason**, and one — `cr-assessment-retrieves-earlier-taught-material`
  — becomes answerable at all on drafts whose delivered assessment is a single question block.
- **The alignment result may become partly tautological.** The proposals are written by the same
  pipeline that wrote the objectives, so agreement between them is evidence of internal
  consistency, which is weaker than evidence of good assessment. `cr-assessment-matches-the-declared-verification`
  is the one at risk of losing discriminating power. This is **measured, not argued**: the same
  drafts are judged with and without proposals and the two results compared. The instrument
  records the same caution as an alternative explanation of its claim.
- **The assessor must be re-ratified** (ADR-0019), and the version that reads the new corpus is
  a new assessor identity (ADR-0016 clause 2), so no calibration transfers across it.
- **The fitness denominator moves for this lineage**, so values computed before and after are
  not comparable (ADR-0023 §7). Anyone already running generations has to be told when this
  lands.
- **The adapter's extraction identity changes** (`ADAPTER_VERSION`), so the format needs a fresh
  `ExtractionAccepted` and every LearnpackV2 content needs re-profiling.

## Alternatives considered

- **Two ids: `assessment_proposals` beside `lesson_assessment_items`** → rejected, and it is the
  closest call here. It makes conflating the two impossible: a criterion about shipped work
  requires the shipped id and there is nothing to forget. It was rejected because `requires` is
  conjunctive — any absent datum derives `no_evidence` — so a draft offering only proposals, or
  only quizzes, would be silenced on all three criteria while holding exactly the evidence they
  ask for. Three of the five drafts on hand are one block away from the first case, which is the
  direction this format is moving, and silencing there would reproduce the very defect this ADR
  exists to remove.
- **Widening `lesson_assessment_items` to include proposals** → rejected. The id is global
  across instruments (ADR-0014) and its definition is the assessment a content *carries*; making
  one format's adapter mean something else by it is how two readers come to disagree about what
  a datum says. It would also erase the distinction entirely rather than moving it into a field.
- **Declaring the `lesson_activities` capability from proposals** → rejected, unchanged from the
  adapter's original reasoning: a proposal is not an exercise, and the criteria that require
  activities ask about the exercise's pedagogy.
- **Leaving it alone and reading the failures as generator defects** → rejected once the five
  objectives were checked by hand against the proposals. A judge that is systematically right
  about a corpus that is systematically incomplete produces confident wrong findings, which is
  worse than an abstention.

## References

ADR-0009 (extraction without inference; absence is a result — why an empty list was never an
option) · ADR-0014 (who mints a data requirement, and *similar-but-different → new id*) ·
ADR-0020 (`value_domain` declared and checked — the shape the adapter conforms to) · ADR-0021
(the fail derived from absence) · ADR-0012 (extraction acceptance is a human act, per adapter
version) · ADR-0027 (package intake by mechanical discovery — where artifacts come from) ·
ADR-0032 (an instrument forks by claim, not by format — §3 is the test applied in §7 above) ·
ADR-0016 / ADR-0019 (assessor identity and ratification per instrument version) · ADR-0023 §7
(equal coverage is what makes two fitness values comparable) ·
`docs/seed/instruments/course-drafts-qa-v7.yaml` (the claim and the three criteria this
decision rewrites).
