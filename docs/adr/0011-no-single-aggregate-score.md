# ADR-0011 — No single aggregate score: the result is a per-criterion profile

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation / Reporting

## Context

Today Reporting computes, in addition to the per-criterion average, an **overall average** per
content and a global one (`overall_average` / `global_average` in
`backend/app/modules/reporting/application/aggregation.py`). It is the most intuitive way to
answer "how good is this course?".

Three problems make it untenable when opening the engine:

1. **Pedagogical quality has no universally accepted composition formula.** Averaging
   criteria grounded in different frameworks (Bloom, Biggs, Merrill, Schmidt) assumes they are
   commensurable and equally weighted. Nothing justifies that.
2. **An average hides exactly what matters.** A course with excellent objectives and zero
   alignment can tie with an evenly mediocre one. The actionable information —what is wrong— is
   lost in the number.
3. **With tri-state outcomes (ADR-0010) the average is no longer defined.** What value does a
   `not_applicable` have? And a `no_evidence`? Any silent choice lies: if "no evidence"
   counts as the minimum, *absent* is confused with *bad*; if it is excluded, an empty course gets
   a perfect grade.

Three mature and independent sources avoid the single number: `k12-teacher-skills` —*"track
per-criterion pass rates rather than aggregates, since aggregate scores mask specific gaps"*—; the
Achieve OER Rubrics, eight rubrics with the explicit rule of being scored **independently**; and
Quality Matters, which even with weights does not use an average: it uses a threshold **plus**
mandatory standards that must all be met.

## Decision

**The result of evaluating a content is a per-criterion profile, not a score.**

1. **No single score aggregating distinct criteria is published**, neither per content nor
   globally. `overall_average` / `global_average` are removed.
2. **Aggregating *the same* criterion across assessors continues.** Averaging criterion C over 3
   evaluators is legitimate and is what inter-rater dispersion needs. What is forbidden is
   collapsing **across distinct criteria**.
3. **Every result is reported alongside its coverage**: how many criteria were evaluated, how many
   did not apply, how many were left without evidence. **A result without coverage is misleading.**
4. **Denominator rules:** `not_applicable` stays **out**; `no_evidence` stays **in** —if it
   were excluded, a course with nothing evaluable would obtain the best possible result.
5. **Comparing contents is done criterion by criterion**, or by explicitly declared
   subsets (e.g. a dimension), never by a total.

## Relationship with ADR-0006

**It does not supersede it.** ADR-0006 decides *the mechanism* of Reporting (composition via query
ports + aggregation in Python) and the per-criterion inter-rater dispersion; all of that remains in
force. This ADR decides a model question that ADR-0006 left implicit: **what is legitimate to
aggregate**. The per-criterion average and the dispersion from ADR-0006 are kept; the overall
average is retired.

## Consequences

- (+) The report comes to say something actionable: *what* fails, not *how much* it fails in the
  abstract.
- (+) Compatible with the tri-state of ADR-0010 without silent decisions.
- (+) It prevents an apparently objective number from backing a composition nobody grounded.
- (−) **It changes the already-built admin console**, which today shows a per-course and global
  average. That view and its tests must be redone.
- (−) The trivial ranking of courses is lost. It is intentional: that ranking assumed a
  commensurability that does not exist. If ordering is needed later, it will have to be justified
  with an explicit scheme (weights, *gates*) and its own ADR.
- (−) A profile is harder to communicate than a number. It is a presentation problem, and it is
  the right one to have.

## `[future]`

- **Mandatory gates in the style of Quality Matters** (criteria that, if they fail, invalidate the
  whole set regardless of the rest). They fit the profile and require no average, but they demand
  deciding which ones are essential — a pedagogical decision we currently have no grounds to make.
- **Per-criterion weights.** Without data to justify them, they would be arbitrary with an
  appearance of rigor.

## Alternatives considered

- **Keep the overall average as "indicative"** → rejected: every published number gets used as
  authoritative, no matter how many labels it carries.
- **Single score with weights** → rejected for now: we have no empirical basis for the weights,
  and without it a weight is an opinion disguised as measurement. Reconsiderable once the golden
  exists.
- **Score per dimension** (5 numbers instead of 1) → partially accepted in spirit: grouping by
  dimension is a legitimate view, but it requires the same commensurability argument within the
  dimension. Admitted as a presentation grouping, not as a published value.
