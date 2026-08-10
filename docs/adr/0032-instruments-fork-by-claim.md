# ADR-0032 — An instrument forks when its claims change, not when the package format does

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design

## Context

An `Instrument` is an evidential argument: qualities are what we care about, claims assert
something about exactly one quality each (ADR-0026), criteria evidence claims, and data
requirements are what criteria need to be executable. A published version is immutable and a
study pins one — that pin is what reproducibility hangs on.

`bindings` carries `package_format`, so one instrument can be designed for several formats,
and the matching report (`GET /admin/instruments/{version}/matching?package_format=`) exists to
show which criteria a format's extraction cannot feed. Those criteria derive `not_applicable`:
demand the supply side does not meet, reported once per format rather than per course.

Adding `LearnpackV2` made the open question concrete. It is not a poorer LearnpackV1 — it is
the generator's raw output *before* the teacher's processing step, so a package carries
proposals where a finished course carries exercises. Against the current instrument's 27
criteria:

| | LearnpackV1 | LearnpackV2 |
|---|---|---|
| Criteria covered | 23 | 21 |
| Claims with no covered criterion | 2 of 17 | 3 of 17 |

Comparable in volume, and **disjoint in shape**. V2 lights up the three criteria about declared
objectives and audience that V1 leaves dark, and darkens five about practice. Neither is a
subset of the other. Three claims go entirely unevidenced for V2 —
`cl-course-demonstrates-before-practice`, `cl-lessons-offer-application`,
`cl-tasks-grow-from-guided-to-open` — and all three are the Merrill line: demonstrate before
practice, practice that grows from guided to open.

That last fact is what forces a decision. Those claims are not dark because the format declares
less. They are dark because the artifact has not reached the stage where the question means
anything. Asking a draft whether its practice tasks fade their scaffolding is not a finding
about the draft; it is a category error dressed as a gap.

So: is a format whose packages cannot evidence a claim a reason to write a second instrument?

## Decision

**An instrument forks when the claims change. It does not fork because the package format
changes.**

1. **A new format binds to the existing instrument.** Add a `bindings` entry, publish the new
   version, read the matching report. Criteria the format cannot feed derive `not_applicable`
   and are reported as unmet demand. This is the normal path and it needs no new instrument.

2. **`not_applicable` is a report, not a defect.** A criterion the supply side cannot feed is
   demand stated honestly and left unanswered. It is not a hole to be plugged by weakening the
   criterion, and it is not a reason to fork.

3. **A second instrument is justified by a second question.** When the claims themselves
   differ — a different thing is being asserted, about a different artifact or at a different
   stage — the argument is different, and a different argument is a different instrument. The
   test is not "can this format feed my criteria" but "am I asserting the same thing".

4. **Dark claims are the signal, not the trigger.** A claim that no package of a format can
   ever evidence is evidence *that another question exists*, not licence to fork automatically.
   The fork happens when that other question is written down as its own claims.

Concretely for the case at hand: LearnpackV2 binds to `learnpack-course-qa`, and the drafts
instrument exists because *is this a good draft to hand a teacher?* is a different question
from *is this a good course?* — with claims of its own about proposal quality, concept-graph
coverage and whether lesson briefs are actionable. It would be justified even if a single
format served both.

## Consequences

- **The cheap path stays cheap.** Supporting a format ends at a `bindings` entry plus a version
  bump. The runbook for adding a package format keeps its step 6.3 unchanged.
- **Instrument count tracks questions, not formats.** Ten formats and one question stay one
  instrument; one format and two questions are two instruments. This is what keeps the pin a
  study declares meaningful: it names an argument, not a parser.
- **Cross-instrument comparison is not offered, and should not be.** Two instruments assert
  different things; there is no aggregate to compare them on, which is the same reason ADR-0011
  forbids a score across criteria. What remains comparable across formats *within* one
  instrument is per-criterion, on the criteria both feed.
- **The criteria lineage survives.** Criterion and claim ids stay stable across versions of one
  instrument (ADR-0019 accumulates coverage by that lineage). A fork starts a new lineage
  deliberately, rather than colliding ids across two arguments that do not mean the same thing.
- **Ratification is per instrument version (ADR-0019), so a second instrument means ratifying
  its assessors separately.** That cost is real and it is the point: an assessor vouched for
  one argument has not been vouched for another.
- **The data requirement namespace stays shared.** Ids are global across instruments, so a fork
  reuses `lesson_bodies` and `course_descriptor` for free and mints only what its new claims
  demand (ADR-0014's rule decides which is which).

## Alternatives considered

- **One instrument per `PackageFormat`** → rejected. It makes the instrument a property of the
  parser rather than of the question, duplicates every shared criterion across files with ids
  that must not drift, and multiplies ratifications for arguments that are the same argument.
  It also gets the LearnpackV2 case backwards: it would fork for the 5 practice criteria while
  keeping the 18 shared ones duplicated, when what actually differs is the question being
  asked.
- **Weakening the criteria so every format can feed them** → rejected. It buys coverage by
  making the assertion vaguer, and a criterion that any package satisfies evidences nothing.
  ADR-0009's stance — absence is a result — already covers the honest reading.
- **A per-criterion `applies_to` on the format** → rejected as premature and as the wrong
  mechanism. It encodes a stage distinction inside a criterion list and would still leave one
  instrument asserting two different things about two different artifacts; `not_applicable`
  already reports the same fact without pretending the argument is unified.
- **Deciding from first principles instead of measuring** → rejected in method: the matching
  report gives the counts, and the disjointness above is what turned an aesthetic preference
  into a decision.

## References

ADR-0026 (a claim asserts about exactly one quality — the rule that makes "the claims changed"
a checkable statement) · ADR-0011 (no aggregate score across criteria — the same reason
cross-instrument comparison is not offered) · ADR-0019 (coverage by criteria lineage and
ratification per instrument version — what a fork restarts) · ADR-0014 (the shared demand-side
namespace a fork inherits; same meaning → alias or revision, similar-but-different → new id) ·
ADR-0018 / ADR-0009 (declared coverage and absence as a result — why `not_applicable` is a
report) · ADR-0017 (the declared surface of the evaluand is the package — the distinction this
decision extends from surface to stage) · `docs/design/12-define-qa.md` §*Evaluation Design*
(the invariants publish enforces) · `backend/README.md` §*Authoring an instrument* (step 0
applies this decision).
