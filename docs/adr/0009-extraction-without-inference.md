# ADR-0009 — The engine does not infer: only declared, quoted evidence

**Status:** accepted · **Date:** 2026-08 · **DDD context:** content extraction /
Pedagogical Evaluation

## Context

Evaluating a criterion requires the data that criterion measures: to judge objectives with
Revised Bloom, you need the objectives. But not all educational content declares them, and even
when it does, not always in a metadata field.

This creates the temptation to have an LLM **infer** what is missing ("this course seems to teach
X, so its objective would be to understand X") and evaluate over that reconstruction. We must
decide whether to allow it.

## Decision

**The engine evaluates only what the content says. It does not fill in what it does not say.**

1. **All extracted evidence is quoted.** Every element of the `ContentProfile` carries its
   `EvidenceProvenance` with a **locator**: the verbatim quote and where it is in the content.
   No quote, no evidence.
2. **Provenance values:** `declared_structured` (it is in a metadata field) ·
   `declared_in_content` (it is stated textually in the body, with a quote) · `absent`.
   **There is no `inferred`.**
3. **No `confidence` is recorded.** If the rule is "only what is written", what is needed is the
   quote, not a confidence number — which would be the crutch used to justify the reconstruction.
4. **Absence is a result, not missing data.** "This course does not state objectives" is a
   first-class pedagogical finding and is reported as such.
5. **Linking already-declared elements is still extraction**, not inference: linking an
   assessment item to an objective is legitimate when **both ends exist and are quoted**. What is
   forbidden is producing an end that is not there.
6. **Deciding whether a vague statement counts as an objective is judgment, not extraction.**
   "You will learn about loops" is extracted as is; that it is vague is a finding of the
   evaluation, not a failure of the extractor.

## Consequences

- (+) **A real defect is not laundered.** Biggs's constructive alignment —one of the founding
  frameworks— starts from explicit objectives. A course without them has a problem; inferring them
  would turn it into a pass and destroy precisely the most valuable finding.
- (+) **Auditability.** Every score can be traced back to a quote from the content. A
  `QualityJudgment` no longer depends on the extractor's good faith.
- (+) **Extractors become testable with fixtures**, even those that use an LLM: their output is
  a verifiable quote, not a judgment.
- (+) **Reproducibility.** A quotable extraction is stable across runs, which sustains the
  comparability that calibration needs.
- (−) Some content will produce very poor profiles and, therefore, evaluations with a lot of
  absence. **It is the correct result**, but it demands that the report communicate coverage
  alongside the score (see ADR-0011) so that "not evaluated" is not read as "bad".
- (−) It closes the door on evaluating content of very low structural quality with the same rubric
  as well-documented content. Accepted: they are different cases and should look different.

## Outside the engine, allowed

Suggesting **to the author** that they declare objectives —"this course does not state them; from
what can be seen it appears to teach X, consider declaring it"— is a legitimate product feature,
clearly labeled as a suggestion. **It never enters as input to an evaluation or a score.**

## Alternatives considered

- **Allow inference marked as such, with `confidence`**, and let the consumer decide →
  rejected: in practice the score is consumed without reading the provenance, and the marker does
  not prevent a real defect from turning into a passing number. It also contradicts point 4.
- **Infer only when the criterion authorizes it** → rejected: it moves the decision to each
  criterion and guarantees someone will enable it out of convenience; the epistemic problem does
  not change depending on who allows it.
- **Reject content that does not declare what is needed** → rejected: it turns into an error what
  is valuable information about the content.

## References

No mature evaluation practice scores reconstructed evidence: `k12-teacher-skills` scores
"what pass requires" over what is present; Quality Matters judges Met/Not Met over present
evidence; teacher observation protocols score **only what is observed**. Details in
`notes/discover-proceso-bloom-sin-objetivos.md` and `notes/research-motor-evaluacion-multiangulo.md`.
