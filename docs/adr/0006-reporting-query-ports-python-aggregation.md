# ADR-0006 — Reporting: composition via query ports + aggregation in Python

**Status:** accepted · **Date:** 2026-07 · **Context:** Reporting (supporting-generic)

## Context
Reporting reads data from all modules (scores, evaluations, assignments, contents, assessors).
`07-define` (written earlier) said "SQL views/queries over the tables", but the isolation rule was
later hardened (no cross-module JOINs; importing `modules/*/infrastructure` forbidden)
to the point of becoming an architecture test. The contradiction must be resolved and how Reporting
aggregates must be fixed.

## Decision
1. **Composition via query ports + aggregation in Python.** Each owning module exposes its own in its
   `public.py` (evaluation adds a scores query); Reporting composes and computes mean/dispersion
   in Python. Zero new tables; respects the isolation. At MVP scale (~50 courses × 3 SMEs × 5
   criteria ≈ 750 scores) the cost is nil. Use **batch** queries to avoid N+1.
2. **Inter-rater per criterion = simple dispersion:** standard deviation + mean absolute pairwise
   difference + % exact agreement. Interpretable with 2-3 raters, respects the 1-5 ordinal scale,
   no new dependencies. Sufficient to detect conflicting criteria/courses when building the
   golden.
3. **Repetitions from the same assessor:** collapse to **the most recent** per
   `(assessor, content, rubricVersion)` (ADR-0005's definition of repetition — **not** per
   assessor alone: that would collapse distinct courses from the same evaluator), because a human
   re-evaluation is a correction that supersedes; and only then average across assessors — consistent
   with the quorum, which counts distinct assessors.

## Consequences
- (+) Respects the isolation rule (Reporting extractable; nobody couples to its schema).
- (+) No projection machinery or eventual consistency → exact reports for the demo.
- (+) Thin, in line with supporting-generic (`04-strategize`).
- (−) Aggregation in Python does not scale to millions of rows — irrelevant at MVP volume.

## `[future]`
- **Event-fed CQRS projections** (read-model tables) when volume/latency demand
  it — Reporting's target model.
- **Formal agreement metric** (Krippendorff's α: variable N raters, ordinal) when automatic
  sources need to be calibrated.
- **Intentional automatic sampling** (e.g. `LLMJudge` ×N): collapse by **mean** per assessor +
  report **intra-assessor dispersion** (self-consistency) separately — a different aggregation,
  for a different purpose (calibration), not the human MVP's.

## Alternatives
- **SQL views with cross-module JOINs** (what 07-define said) → rejected: breaks the isolation,
  turns Reporting into a privileged module that blocks others' schema changes, would require exempting
  Reporting from the architecture test.
- **Event-driven CQRS projections already in the MVP** → rejected: over-engineering for the current
  volume; unnecessary eventual consistency.
