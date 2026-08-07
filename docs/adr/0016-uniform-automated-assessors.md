# ADR-0016 — Uniform automated assessors: the per-criterion mechanism is internal to the assessor

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Evaluation Design · Identity

## Context

The glossary defined four types of `EvaluationSource`: `HumanExpert`, `LLMJudge`,
`DeterministicVerifier` and `HybridVerifier`, with `SourceConfiguration` as the config that
defines an `Assessor` of type `LLMJudge`. When designing the slice 2 code plan
(`design/13-code-qa.md`) that taxonomy showed three problems:

1. **The deterministic/LLM distinction does not cut along identities but along a spectrum.**
   An "LLM judge" is never just an LLM: it is always deterministic code orchestrating calls
   to a model. And within the same instrument, some criteria are naturally computable
   ("at least 3 declared objectives") and others call for semantic judgment ("each
   objective uses an observable verb") — the ideal mechanism varies **per criterion**, not
   per instrument nor per "source type". The glossary itself hinted at it: `HybridVerifier`
   was "the Hybrid Norm" — if the hybrid is the norm, the other two are degenerate points
   of the spectrum.
2. **Typing the judge by mechanism forces artificial choices**: either the judge's identity
   is fragmented per criterion (who produced *the evaluation*?), or the whole instrument is
   tied to a mechanism that does not belong to it.
3. **The realization tempted putting the execution reference inside the criterion**
   (a `check_spec` pointing to functions). That breaks the criterion being
   source-agnostic: the same condition must be judgeable by a human, pure code, or code
   with an LLM.

## Decision

**The source taxonomy is reduced to `human | automated`; everything else is internal detail
of the automated assessor.**

1. **Two types, with a real structural difference:** humans enter through
   assignments/UI/asynchrony (ADR-0002/0005, ADR-0015); automated ones through config +
   execution. How much LLM an automated assessor uses defines neither identity nor type —
   it is internal detail of its per-criterion execution.
2. **The automated assessor is a modular, versioned software artifact**
   (`{name, version, config}`): a package of its own with an **internal
   `criterion_id → executor` mapping**. Any change (code, mapping, model, prompt, internal
   threshold) ⇒ new version ⇒ **another identity** (calibration does not transfer —
   invalidation by identity, as already governed `SourceConfiguration`).
3. **Each automated assessor declares a target instrument** (one version): it owes itself
   to the criteria of that instrument. Relationship: instrument 1 → 0..N automated
   assessors; humans are not tied to any. Target coverage is **validated at registration**
   (complete mapping over all criteria). Independent assessors over the same
   instrument are comparable — the dispersion/agreement case that ADR-0005 enables.
4. **The instrument remains 100% declarative.** It never references executors, checks or
   mechanisms. Normative thresholds live in the criterion's `pass_condition` (ADR-0010);
   the executor realizes them. It is the same move as ADR-0014 on the other edge: the
   supply side (assessor) declares its capabilities against the ids of the norm side
   (criteria) — the mapping lives on the supply side.
5. **The criterion's `eligible_sources` takes values `{human, automated}`.**
   `SourceConfiguration` is generalized: it is the config of any automated assessor.
6. Consistency between the normative condition (text) and its realization (code) is not
   verifiable by tests: it is verified by the **human layer 2** (ADR-0015) over quoted
   outcomes.

## Consequences

- (+) Modular and independent assessors: two people can build different approaches for the
  same instrument without sharing identity or stepping on each other; comparing their
  results uses the existing machinery (repetitions + dispersion, ADR-0005/0006).
- (+) The instrument is portable across assessors (human today, code tomorrow, LLM later)
  without touching it.
- (+) The spurious identity churn of a shared "check library" disappears (where any change
  invalidated all judges at once).
- (+) The provenance chain does not change: `assessorId` remains the key, for humans and
  automated ones.
- (−) A new criterion in the target demands a new version of the assessor (teaching the
  grader to grade a new question IS changing the grader). Correct but laborious; mitigable
  with bottom-up shared utilities (with the discipline of bumping the version when
  touching them).
- (−) The "deterministic" property (bit-for-bit reproducibility, no sampling noise) stops
  being a type; when calibration needs to distinguish it (self-consistency, ADR-0006
  `[future]`), it is read from the assessor's config.
- (−) The GLOSSARY must rewrite its Source axis; `LLMJudge`, `DeterministicVerifier` and
  `HybridVerifier` move to the equivalence table as industry/legacy vocabulary.

## Alternatives considered

- **Keeping the four-type taxonomy** → rejected: it types by mechanism what varies per
  criterion; it forces artificial identities and contributes no structural distinction that
  `human | automated` does not cover.
- **Execution reference (`check_spec`) inside the criterion** → rejected: it breaks the
  source-agnostic criterion and drags executor vocabulary into the instrument's data.
- **A shared check library as the single deterministic assessor** → rejected: any change in
  any function changed the identity of all judges (spurious invalidation), and it
  prevented independent experimentation with assessors in parallel.
- **An interpreted condition mini-DSL** → rejected for now: it requires designing, parsing,
  validating and versioning a language of one's own with no present consumer; errors go
  from "failing test" to "expression misinterpreted at runtime". Reconsideration trigger:
  authoring getting blocked waiting for executor code.

## References

Instrument/rater separation in psychometrics (inter-rater reliability; grader
calibration) · the *judge drift* problem and "version your judge" in the LLM-evals
industry · `design/13-code-qa.md` §3.5 (realization) · full discussion in the code-plan
design session (notes/, cycle complete).
