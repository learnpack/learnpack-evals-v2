# ADR-0015 — Human reference in two layers: panel per quality + sampled verification

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Evaluation Studies · Golden Dataset · Calibration `[future]`

## Context

Expert human evaluation is expensive in time and money; a small team cannot run SME
campaigns every time an instrument changes. At the same time, human judgment is the source
for answering the central calibration question: *how much do non-human assessors agree
with the experts?*

The pre-close review of Define also found a structural gap: instrument execution requires
`ContentProfile` (DP17/DP18 — coordinates with `adapterVersion`, mechanical derivation of
the tri-state), which meant **a human could not evaluate content without an accepted
adapter** — blocking the path "I evaluate with humans while I build the adapter". The gap
existed because the model merged **two distinct human roles**.

Industry practice is settled: align judges against a **set labeled by humans once** and
reuse it on every iteration of the judge (kappa ≥ 0.60 as a typical threshold, ~50 labeled
items before automating); **sampled human verification at 5–10%** with queues prioritized
by low agreement; periodic re-sampling against drift. EvalGen (UIST 2024) contributes the
*catch-22*: it is by grading outputs that humans discover their own criteria — human
calibration feeds the design, it does not merely control it.

## Decision

**Human participation has two modes, with different rules; the reference is bought once and
reused; continuous verification is sampled.**

1. **Reference panel mode (layer 1).** SMEs judge the **qualities directly**, reading the
   content — **outside instrument execution, without a profile**. Elicitation is holistic
   per quality/dimension (ordinal scale): the appropriate form for direct construct
   judgment (the Achieve OER pattern). **It is not subject to ADR-0010**, whose scope is
   the criteria of the evidential argument — this is another artifact with other rules.
2. **Assessor/verifier mode (layer 2).** Within instrument execution, the human works
   **on the profile**, verifying **quoted** outcomes ("the system says there are no
   objectives; here is the extraction — correct?"). The profile prerequisite (DP17/DP18)
   **stays intact**: the gap is not patched, it dissolves — the need that seemed
   blocked is served by the reference mode.
3. **`Rubric v1` is NOT migrated: it stabilizes as the layer-1 reference instrument**
   (criterion↔dimension 1:1, 1–5 scale). Its stability is a **feature**: a reference that
   changes is not a reference. The debt "migrate v1 to the ADR-0010 form" is cancelled;
   it is replaced by a light review (anchors, definitions) before the first reference
   campaign.
4. **The instrument↔reference comparison does not sum anything: validity coefficients per
   claim.** Each claim is correlated with the human score of **its** quality across the
   contents of the set — per-claim diagnosis ("which ones track expert judgment"), never
   sums to dimension (the ADR-0011 argument applied to calibration). Agreement metrics are
   **calibration artifacts** (like the dispersion of ADR-0006), not published judgments.
5. **The ceiling is measured first:** judge-human agreement is always reported alongside
   human-human agreement (inter-rater, ADR-0006), which is its upper bound.
6. **Sampled verification** (layer 2): configurable %, queues prioritized by disagreement,
   challenges and new criteria; periodic re-sampling. ADR-0009/0010 made this cheap by
   construction: **verifying a quoted check costs minutes; producing a holistic judgment,
   hours.**
7. **Incremental refresh of the reference** when the content distribution changes (the
   paired briefs of ADR — DP12 — help extend it comparably). No full re-campaigns.

## Consequences

- (+) Resolves gap #1 of the review **without new machinery**: the reference mode uses what
  is already built (Rubric v1 + campaigns + quorum + `GoldenDataset`).
- (+) One expensive campaign, reused against **all** instrument versions (anchored in the
  qualities — the stable column of the language); continuous validation cheap and
  prioritizable.
- (+) Actionable diagnosis: validity per claim, not correlations per dimension.
- (+) EvalGen's catch-22 is captured: human verification feeds loop B.
- (−) The holistic reference is noisy: the ceiling is set by the human inter-rater — it
  must be measured and reported, not assumed.
- (−) Construct drift to watch: claims reference `qualityId` with definition; changes in
  the reading of a quality silently invalidate comparisons if not reviewed.
- (−) `GoldenDataset` gains an additional role (instrument calibration reference, besides
  ground truth for assessor calibration `[future]`); its canvas is adjusted when promoting.

## Alternatives considered

- **Humans executing new instruments without a profile** (with their own quotes) → rejected:
  it would break the mechanical derivation of DP18 and duplicate the extractor's role
  inside the act of judgment; the real need is covered by the reference mode, with existing
  machinery.
- **Migrating Rubric v1 to checks** (the previous plan, recorded in STATUS) → replaced: it
  would destroy the stable reference and its holistic form — which is the appropriate one
  for direct construct elicitation.
- **SME campaigns per instrument version** → unviable: it is the problem to solve, not an
  option.
- **Comparing by summing scores to quality/dimension** (the original idea) → rejected: the
  sum destroys the diagnosis — it does not say *which* claim diverges (same argument as
  ADR-0011).

## References

Judge calibration with human annotations: https://galileo.ai/blog/calibrate-llm-judge-human-annotations ·
https://www.evidentlyai.com/blog/how-to-align-llm-judge-with-human-labels ·
https://www.langchain.com/resources/llm-as-a-judge · HITL and annotation queues:
https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026 ·
EvalGen, "Who Validates the Validators?" (UIST 2024): https://arxiv.org/abs/2404.12272 ·
Full reasoning in `notes/` (slice 2 exploration).
