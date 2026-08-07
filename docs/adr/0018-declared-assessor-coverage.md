# ADR-0018 — Declared coverage of the automated assessor: explicit abstentions and the `not_assessed` state

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Identity

## Context

ADR-0016 (clause 3) established that each automated assessor declares a target instrument
and that "target coverage is **validated at registration** (complete mapping over all
criteria)". The code plan realizes it the same way (13-code §3.5: the registry "validates
at registration that the mapping covers all the target's criteria").

The first real instrument (`learnpack-course-qa-v1`, 5 claims / 11 criteria) breaks that
assumption: it contains pedagogical-judgment criteria — `cr-module-single-topic`,
`cr-arc-character`, `cr-modules-intro-then-apply`, `cr-objectives-observable-verbs` — that
a pure-code assessor cannot execute, and the MVP has no LLM adapter (the LLM mechanism
is `[future]`). Complying with the letter of clause 3 leaves two exits, both bad:
blocking the registration of every pure-code assessor against this instrument, or forcing
executors that pretend to judge what they cannot.

Omitting those criteria is no exit either: 12-define (Pedagogical Evaluation, inv. 1)
requires **exact coverage** — "one outcome per criterion of the `instrumentVersion` —
nothing missing, nothing extra" — and an assessor that leaves criteria without an outcome
breaks it, making an omission bug indistinguishable from a known limitation.

## Decision

**The coverage required at registration is declared-exhaustive, not executed-exhaustive;
what is not executable produces a fifth outcome state, `not_assessed`, derived mechanically.**

1. **Declared coverage.** The assessor's package declares two disjoint sets: the
   `criterion_id → executor` mapping and a list of **abstentions**
   (`criterion_id → short reason`, e.g. "requires semantic judgment"). Registration
   validation becomes: *mapping ∪ abstentions == target criteria, with no overlap*.
   Exactly what ADR-0016 wanted to catch is preserved — a new criterion in the
   instrument still forces a new assessor version and a conscious decision
   (execute it or abstain) — but the decision can be honest.
2. **`not_assessed`.** Each abstained criterion produces an explicit row in
   `criterion_outcomes` with outcome `not_assessed`, without a quote (the quote
   requirement remains only for `pass`/`fail`). Semantics: *the data is present and the
   criterion is judgeable; this assessor declared it cannot judge it*. It is a distinct
   cause from `no_evidence` (the data is absent from the content) and from
   `not_applicable` (no format capability or excluded conditional): three causes, three
   remedies — better generator · better extraction or format · better assessor.
3. **The derivation remains mechanical.** The invariant "non-scored outcomes are
   derived mechanically, never decided by the assessor" is preserved: the abstention is
   declared at **registration** and is part of the immutable identity of the assessor's
   version (ADR-0016: any change ⇒ new version). In `EvaluateContent`, the
   judgeable criteria that fall in the abstention list become `not_assessed` by
   derivation, without assessor intervention at runtime.
4. **Sufficiency and denominator.** Under conjunctive sufficiency (13-code §7.1),
   `not_assessed` falls into "any other case": the claim remains `insufficient` — neither
   supported nor refuted; the rule does not change. In the ADR-0011 denominator,
   `not_assessed` stays **inside** (like `no_evidence`); only `not_applicable` stays
   out. The per-claim `evidence_basis` now counts
   `{pass, fail, no_evidence, not_applicable, not_assessed}` and the judgment's coverage
   goes from a triple to a quadruple (assessed / not applicable / no evidence / no
   capable assessor): each "insufficient" is qualified with its cause.
5. **Exact coverage is preserved by construction**: one outcome per criterion of the
   snapshot, now over five states. Realization deltas over 13-code §3.5 (frozen snapshot
   this ADR amends): the `criterion_outcomes` CHECK adds
   `'not_assessed'`; the registry validation validates the disjoint union; the
   `evidence_basis` counts and the judgment's `coverage` jsonb add the new cause.

## Relationship with ADR-0016

**It does not supersede it.** ADR-0016 decides the `human | automated` taxonomy, the
assessor as a versioned modular artifact with a target instrument, and invalidation by
identity — all of that remains in force. This ADR refines its clause 3: registration
validation stops requiring a complete executable mapping and starts requiring
**complete declaration** (mapping + abstentions). The purpose of the clause — that no
target criterion be left without a conscious decision by the assessor's author — is
fulfilled all the same.

## Consequences

- (+) The system tells the truth: judgment claims remain `insufficient` with a visible
  cause ("no capable assessor"), neither falsely judged nor silently omitted. The
  accumulated `not_assessed` are the **visible backlog** of the LLM (or human) assessor:
  the demand that justifies prioritizing it, measurable per instrument and per criterion.
- (+) Registration still catches forgotten criteria: adding a criterion to the instrument
  without touching the assessor still fails the disjoint-union validation.
- (+) No change to sufficiency nor to the denominator rule: only a distinguishable
  cause is added.
- (−) One more state in the enum, in queries and in the future judgments/reports UI.
- (−) Reports must distinguish the causes of `insufficient` so the state is not read
  as noise; `evidence_basis` makes it possible, the studies must do it (the caveats
  rule of 12-define already requires it).
- (−) The GLOSSARY rewrites its "tri-state" (Criterion, CriterionScore, QualityJudgment,
  equivalence table): the outcome becomes
  `scored (pass/fail) | not_applicable | no_evidence | not_assessed`.

## Alternatives considered

- **Stub executors that "cover" everything by returning abstention** → rejected: complies
  with the letter of ADR-0016 with pure ceremony (one stub per judgment criterion), and
  the fifth state is needed anyway so the outcome tells the truth.
- **Mapping the abstention to `no_evidence`** → rejected: it lies — it conflates "absent
  data" with "absent judge" and breaks the cause/consequence distinction of 12-define
  (Evaluation Design inv. 3); the studies could not separate what is fixed with better
  generation and what with a better assessor.
- **Omitting the row (no outcome for what is abstained)** → rejected: absence-as-data;
  it breaks exact coverage by construction (PE inv. 1) and an omission bug becomes
  indistinguishable from a deliberate abstention.
- **Relaxing validation without explicit abstention** (accepting a partial mapping) →
  rejected: a new criterion in the target would go unnoticed — exactly the silent churn
  that clause 3 of ADR-0016 wanted to prevent.

## References

ADR-0016 §3 (the refined clause) · ADR-0011 (denominator rule: `not_applicable`
out, the rest in) · ADR-0010 (outcome + quote) · ADR-0015 (the human layer 2
verifies norm/realization consistency; the `not_assessed` are also its natural work
queue) · 12-define: Pedagogical Evaluation inv. 1–2, Evaluation Design inv. 3,
Content Profiling inv. 3 · 13-code §3.5 and §7.1 (the realization this ADR amends) ·
the `learnpack-course-qa-v1` instrument (the four judgment criteria that originated the
decision).
