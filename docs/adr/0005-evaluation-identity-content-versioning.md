# ADR-0005 — `Evaluation` identity, content versioning and anti-duplication in the `Assignment`

**Status:** accepted · **Date:** 2026-07 · **Context:** Evaluation · Content Registry ·
Orchestration

## Context
The previous design gave `Evaluation` the identity `(assessor, content, rubricVersion)` with
uniqueness. Two cases break it:
1. **Repetitions from the same source.** An `LLMJudge` (or even a human) may evaluate the
   same `(content, rubric)` **N times** to measure dispersion (deviation, self-consistency,
   voting). Uniqueness prevents it.
2. **Content versions.** Content evolves (LearnpackV1 regenerates/fixes a course).
   It is useful to evaluate the same course at `v1`, `v2`… with the same rubric (improvement/regression).
   Without a version in the model, it cannot be done.

The root cause: *the judgment* was conflated with *the run that produced it*, and a constraint that
was really the human MVP's anti-duplication was made part of the aggregate's identity.

## Decision
1. **`Evaluation` = a concrete act with its own id.** Identity = `evaluationId` (surrogate) +
   coordinates `{assessorId, contentId (version), rubricVersion, attempt/occurredAt}`. **No**
   uniqueness by `(assessor, content, rubric)`: repetitions **coexist**.
   - Statistical dispersion is computed per **concrete `Assessor`** (same `SourceConfiguration`);
     changing the config = another `Assessor`.
2. **First-class content versioning.** Each `contents` record is a **version**
   (`contentId` = version); logical content = `(generatingSystem, externalId)`; uniqueness
   `(generatingSystem, externalId, version)`. MVP: `version` defaults to `"1"`.
3. **Human anti-duplication in the `Assignment`, not in `Evaluation`.** ≤1 active assignment per
   `(campaign, content, assessor)`, fulfilled with **one** submission; re-submitting over one already
   `Submitted` → **409**. Since quorum is counted by `assignments submitted` (ADR-0002), an SME
   cannot inflate the count.

## Consequences
- (+) Correct for `LLMJudge` (repetitions/dispersion), calibration (deviation per `Assessor`) and
  comparison across content versions — all `[future]`, but the model already supports it.
- (+) The human MVP behaves the same (an SME evaluates each course once per campaign), but via the
  assignment rule, not via the aggregate's identity.
- (+) `contentVersion` from day 1 avoids redoing migrations when versioning.
- (−) Aggregation (mean/deviation) over repetitions is the responsibility of `ScoringPolicy`/
  Reporting, not of a uniqueness constraint.

## Alternatives
- **Keeping the `(assessor, content, rubric)` uniqueness** → rejected: makes repetitions and
  versions impossible; conflates judgment with run.
- **Tagging `Evaluation` with `campaign_id`** → rejected in ADR-0002 (breaks multi-campaign and the
  correct identity).
