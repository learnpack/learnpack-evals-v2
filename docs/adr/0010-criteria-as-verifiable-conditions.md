# ADR-0010 — Criteria are verifiable conditions, not appreciation scales

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Rubric Authoring / Pedagogical
Evaluation

## Context

`Rubric v1` defines 5 criteria, one per pedagogical dimension, each with a 1–5 scale and generic
anchors (`docs/seed/rubric-v1.json`, `07-define.md`). Each criterion collapses several qualities
into an appreciation question: *"how good is the quality of the objectives?"*.

Opening the engine to automatic sources exposes two problems with that form:

1. **A deterministic verifier does not produce a 3.7.** It produces a boolean or a measurement
   with units. Mapping that to 1–5 requires arbitrary thresholds, and all the subjectivity
   concentrates in an opaque `ScoringPolicy`.
2. **An appreciation scale is not auditable.** "The objectives are a 3" cannot be traced,
   discussed or reproduced. "Fewer than 3 declared objectives" can.

Moreover, two mature and independent systems converged on the opposite of what we did:
`k12-teacher-skills` uses binary criteria (pass/fail) with an explicit condition —*"At least 3
misconceptions or anticipated challenges named"*, *"All three components in every entry"*— and
recovers nuance by having **many**; Quality Matters judges **Met / Not Met** per standard.

## Decision

**The unit of judgment is a verifiable condition over the content, not a point on a scale.**

1. **Every `EvaluationCriterion` defines an explicit, scoreable pass condition**
   (*what pass requires*): a statement that over a given content is true or false. It is a
   field of the criterion, distinct from its statement and its guidance.
2. **The criterion also enumerates its failure modes**, with an example of the bad case when it
   helps (*"Fail = quote by code only, paraphrase, or wording variation"*). It makes the judge
   consistent, whether human or LLM.
3. **The outcome of a criterion is tri-state**, not a number: `scored` (evaluated) ·
   `not_applicable` (the criterion does not apply to this content) · `no_evidence` (it applies and
   the content does not have it — see ADR-0009). A `scored` criterion resolves to **pass / fail**.
4. **Nuance is recovered with granularity, not with a scale:** a complex quality is
   operationalized into several small, verifiable criteria, not into one with five levels.
5. **The criterion declares the data it needs** from the `ContentProfile`. If they are not
   available, the outcome is `not_applicable` or `no_evidence` depending on the criterion — never
   an invented score or an error.
6. **A criterion whose condition cannot be stated verifiably is a sign that it is badly
   decomposed**, not that it needs a scale.

## Consequences

- (+) **It enables determinism.** A structural check over the `ContentProfile` ("at least 3
  declared objectives", "every assessment references an objective") is computed without an LLM. It
  is the bridge between the `ContentProfile` and the deterministic evaluation we were seeking.
- (+) **Auditable and debatable.** The collaborator can debate a condition; they cannot debate a
  3.7.
- (+) **It improves agreement between evaluators**, human or automatic: a binary condition has
  far less noise than an ordinal scale.
- (+) It fits ADR-0011: pass rates per criterion is what gets reported.
- (−) **Many more criteria are needed.** k12 uses 35 for *one lesson plan*; today we have 5
  for *an entire course*. Writing them is real work — and it is precisely the collaborator's
  work.
- (−) **`Rubric v1` does not comply with this form.** Its 5 criteria are appreciation scales. It
  must be explicitly decided whether to migrate it or mark it legacy (see below). **This ADR does
  not decide that.**
- (−) The apparent granularity of the 1–5 is lost. It is apparent: that granularity was never
  grounded in anything verifiable.

## Scope and migration of `Rubric v1`

This decision governs **the criterion model and every new rubric**. On its own it does not migrate
the existing rubric or the already-built human flow (which assumes `score ∈ [1,5]`).

A relevant fact for that decision: **today there are no evaluations loaded** —human collection was
deprioritized—, so the cost of migrating v1 is minimal *now* and grows as soon as the collaborator
starts iterating on it. It remains an open, conscious decision, recorded in
`notes/estado-exploracion-slice2.md`.

## Alternatives considered

- **Keep 1–5 in all criteria** → rejected: incompatible with deterministic sources without
  arbitrary thresholds, and not auditable.
- **1–5 scale for judgment criteria and binary for computable ones** → rejected: two different
  currencies in the same rubric, impossible to compose or compare; it also pushes toward
  classifying criteria by their implementation instead of by what they assert.
- **Holistic rubric (one global score per dimension)** → rejected: it is the opposite of what the
  evidence recommends; analytic rubrics outperform holistic ones precisely in
  traceability.
- **Scale with anchors per criterion** (instead of generic ones) → improves the problem but does
  not solve it: it is still not verifiable and still does not admit deterministic output.
