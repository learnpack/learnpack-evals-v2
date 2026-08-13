# ADR-0037 — Execution failure is an outcome: the `execution_error` state, the failure budget, and the three-way retry

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Evaluation Design · Evaluation Studies

## Context

ADR-0034 §4 decided that an irrecoverable LLM failure aborts the whole evaluation:
nothing persists, retrying is running `evaluate` again. Its consequences section accepted
the cost knowingly — *"aborting whole evaluations makes long batch runs sensitive to one
flaky criterion"* — and bet that evaluations would stay cheap to re-run.

The calibration campaign falsified the bet. Four evaluations died in one afternoon, each
killed by a **single task degenerating inside an otherwise healthy run**: a 191-entry
evidence loop, a one-sentence repetition that spent three attempts and 24 000 tokens, a
false grounding rejection compounded by the repeat detector, a degenerate tie-break on the
third sample. The bounds that followed (output budgets per task kind, the evidence
ceiling, the no-duplicates rule) cut the **cost** of each death from ~10 minutes to ~35
seconds, but not its **frequency** — and with ~15 LLM calls per evaluation, the
probability that every call survives keeps whole-run survival low. Each death discards a
majority of verdicts that were already correct.

ADR-0034 rejected two alternatives whose written reasons this decision must answer rather
than ignore:

- *"A runtime 'could not judge' outcome → rejected: it hands a non-scored state to the
  assessor at runtime, breaking the ADR-0018 invariant, and it would leak into every
  consumer (fitness denominators, coverage, reports) for what is operationally a retry."*
- *"Persisting the partial evaluation → rejected: coverage is exact by construction (one
  outcome per criterion of the snapshot); a partial row would need a new state to say
  'incomplete', which is the previous alternative in disguise."*

Both objections were sound and both have answers now. The first conflated *the assessor
deciding* a non-scored state with *the machinery deriving* one from a typed failure — a
distinction every testing framework already makes: a test does not decide to error, it
raises, and the harness records `error` as a category distinct from `fail`, never
attributed to the code under test. The second assumed a partial row must break exact
coverage; it breaks nothing if the failed criteria receive an explicit outcome, which is
precisely what the first alternative provides once the deciding/deriving distinction is
made. What was rejected as "the previous alternative in disguise" is, taken together, one
coherent design.

The industry the GLOSSARY's equivalence table tracks has converged on the same shape.
Inspect AI records per-sample errors with their cause, excludes them from metrics, and
bounds partiality with a run-level `fail_on_error` threshold; it also warns that *"retried
samples could have higher success rates due to distribution shift"*. Braintrust excludes
null scores from aggregates. Ragas is the counterexample: it represents judge failure as a
bare `NaN`, and its users systematically confuse "scored low" with "did not score".
Large-scale educational measurement — this system's own discipline — distinguishes
*omitted*, *not reached* and *not administered* responses, treats them differently in
scoring, and has documented that changing the treatment changed country rankings: how
missing judgments enter a denominator is a substantive decision, and missingness that
correlates with the thing measured (nonignorable, MNAR) is the named risk.

## Decision

**An execution failure produces a sixth outcome state, `execution_error`, derived
mechanically from a typed failure the assessor raises; a failure budget bounds how partial
a persisted evaluation may be; and the retry policy becomes three-way, with degeneration
retried on a clean conversation.**

1. **The sixth state, and who mints it.** The outcome vocabulary becomes
   `pass · fail · no_evidence · not_applicable · not_assessed · execution_error`.
   Executors keep producing only `pass`/`fail` — nothing in their result type changes.
   When a criterion's execution raises the assessor's typed error, the **derivation**
   catches it at the executor boundary and mints `execution_error` for that criterion,
   exactly as it mints the other non-scored states from declared facts. The ADR-0018
   invariant is thereby **refined, not broken**: non-scored outcomes are still derived
   mechanically and the assessor still decides nothing at runtime — it *fails*, with a
   typed exception, and failing is not deciding. Semantics of the state: **a statement
   about this evaluation's execution, never about the content** — distinct from
   `not_assessed` ("this assessor's identity declares it cannot judge this") as a fact of
   one run rather than a fact of an artifact. The row carries no quote and no
   `failure_mode` (both belong to verdicts) and **must carry its cause**: which task
   failed and the error class, so a reader can tell a timeout from a degeneration loop.

2. **Task grain inside the assessor, criterion grain in the domain.** The unit that fails
   is the assessor's internal task, and one task may feed several criteria (the assessment
   mapping feeds two). The domain keeps its grain — one outcome per criterion — and the
   assessor realizes task honesty by **memoizing failures** the way it already memoizes
   successes: every criterion consuming a failed task raises the same typed error, cheaply,
   so all of them degrade together with one cause and the model is not re-asked a question
   that just degenerated.

3. **The failure budget: ADR-0034 §4 becomes the degenerate case, not a dead decision.**
   An evaluation tolerates a bounded number of `execution_error` outcomes; past the bound
   it aborts whole, persisting nothing — the existing path. The bound is a named domain
   constant of the derivation (a proportion of the criteria mapped for execution), chosen
   at implementation and reviewed like any decision constant; its effect is checkable
   because the failure counts travel with the evaluation. A mostly-dead evaluation is not
   worth persisting: below the bound, a flaky task costs its criteria; at or past it, the
   run was not an evaluation. The superseded clause survives as this budget's zero point.

4. **Exact coverage is preserved by construction, over six states.** One outcome per
   criterion of the snapshot; the three guards (the derivation loop, the aggregate's
   completeness check, the judgment's coverage check) keep their shape. Realization
   deltas: the `criterion_outcomes` CHECK adds `'execution_error'`; a nullable cause
   column constrained to the new state; the quote/failure-mode CHECKs exclude it; the
   domain validator admits it with cause and without quote.

5. **Judgment semantics: `insufficient`, with the cause visible.** Under conjunctive
   sufficiency `execution_error` falls into "any other case": the claim is neither
   supported nor refuted. `evidence_basis` counts six states; the judgment's `coverage`
   gains the new cause; `insufficiencyCause` in the study report names `execution_error`
   instead of falling through to `"unknown"`. A claim whose evidencing criteria are all
   `not_applicable` is still excluded from the judgment; `execution_error` never excludes
   a claim — a gap in this run must stay visible in it. In the ADR-0011/0018 QA
   denominator the state sits **inside**, like `not_assessed`: hiding it would overstate
   what this evaluation knows.

6. **Fitness: outside the denominator, with the failure published beside the value.** The
   fitness charges the generator for the generator's faults; an execution failure is ours.
   `execution_error` joins `not_assessed` and `not_applicable` in the excluded set —
   the same same-state-two-purposes divergence ADR-0023 clause 3 already governs. Two
   additions are load-bearing, not decoration. First, the coverage payload that travels
   with every value gains the `execution_error` count: two runs of the same content under
   the same assessor may now compute over different populations for reasons of execution
   rather than declared coverage, so ADR-0023 §7's equal-coverage rule extends to it — the
   GA compares only where that count permits. Second, the projection **stops discarding
   unknown outcome states silently**: a state its partition does not know is an error, not
   a dropped row. Missingness here is plausibly nonignorable — degeneration shows up on
   specific (content, criterion) pairs, so failure may correlate with content — which is
   exactly why the counts are published rather than the rows silently vanishing.

7. **The retry policy is three-way, and the failure taxonomy stops collapsing.** The
   assessor's shared error type gains a machine-readable kind (plumbing, not identity),
   preserving the transport/configuration/response distinction the platform client already
   makes, because the policy needs it:

   - **Contract violations** (schema, grounding, undeclared failure mode) keep the
     feedback retry as measured and working — actionable feedback fixed real answers.
   - **Degeneration** (verbatim repetition, runaway lists, an unusable capped answer)
     gets **one retry on a clean conversation** — `messages` rebuilt from scratch, never
     the broken answer fed back, since feeding a loop back puts the loop in the context
     and measurably raises the retry's error rate. Bounded to one: a second identical
     degeneration is the poison case, and it degrades.
   - **Transport, configuration and `finish_reason: length`** are never clean-retried:
     transport has its own backoff, and the other two are deterministic.

   Verdicts that arrive after a clean retry are a **shifted population**; each task
   reports its retry count as a metric so calibration can distinguish them. The retry
   loop and its wording live in the assessor package: this clause is an identity change
   and ships as a new `drafts-hybrid` version, inheriting no calibration — which is the
   system working, not a cost to engineer around.

8. **What the reader sees is a malfunction, never a verdict.** Every surface that renders
   outcomes renders `execution_error` as its own state with its cause — the calibration
   page (whose summary must stop filtering unknown states into invisibility), the
   per-criterion table, the study report, whose caveats gain an entry counting execution
   errors alongside `contentsWithoutJudgment`. Publishing a study with such rows is
   legitimate and visible, never silent; ratification is untouched — it reads declared
   coverage, not outcomes.

## Consequences

- (+) A degenerating task costs its criteria instead of the evaluation. Calibration
  campaigns stop dying wholesale; the verdicts that were already sound persist.
- (+) The supersession is a generalization: the all-or-nothing shape survives as the
  failure budget's limit case, and the abort path stays exercised.
- (+) The Ragas failure mode is structurally closed: no silent drops, no bare-NaN
  equivalent — every consumer either knows the six states or fails loudly.
- (+) Clean-retry reduces failure frequency before anything degrades, and the retry-count
  metric keeps the shifted population distinguishable.
- (−) A sixth state ripples through every exhaustive enumeration: the domain tuple and
  validator, `_BASIS_KEYS`, the fitness partition, the DB CHECK (migration), DTO comment
  contracts, the frontend union, badges, order list and caveats, and the tests that pin
  the five-state partitions. The surface is mapped; none of it is optional.
- (−) Fitness comparability degrades in a new way: execution variance, not just assessor
  sets, can split populations between runs of the same content. Published counts and the
  budget bound it; they do not remove it. If failure correlates with content quality
  (MNAR), exclusion biases the signal — the counts exist so that bias is checkable.
- (−) The GLOSSARY rewrites the outcome vocabulary again (five → six), and reports/UI
  must keep three kinds of "no verdict" (`no_evidence`, `not_assessed`,
  `execution_error`) legible as three different remedies: better generator, better
  assessor, better run.
- (−) `drafts-hybrid` bumps for the retry change and inherits no calibration. Deliberate:
  a judge whose retry conversation changed is a different judge.

## Alternatives considered

- **A runtime "could not judge" outcome decided by the assessor** → still rejected, for
  ADR-0018's reason. What this ADR adopts is categorically different: the assessor raises
  a typed failure and the derivation derives — the same mechanical path as every other
  non-scored state. The xUnit precedent is exactly this line: tests raise, harnesses
  record.
- **An absent row plus an evaluation-level attribute** (the five-state vocabulary kept
  intact) → rejected: exact coverage has three guards that treat a missing row as a bug,
  and ADR-0018 already rejected omission as absence-as-data; the judgment must still
  decide what a claim does when an evidencing criterion was not judged, so the conceptual
  cost is paid without buying visibility per criterion.
- **Clean retry alone, no new state** → rejected as the sole measure: it lowers frequency,
  not to zero, and the moment a retry budget exhausts the state exists anyway or the run
  dies — which is the status quo this ADR ends.
- **Scoring on the partial state reached before the error** (Inspect's `score_on_error`)
  → rejected: a half-judgment is not a verdict, and every scored outcome here owes a
  grounded quote.
- **Representing the failure as null/NaN in read models instead of a state** → rejected on
  the documented Ragas experience: silent representations get read as scores.
- **Caching responses across runs to sidestep re-judging** → rejected, actively harmful
  now: repeated runs of the same content are the diagnostic instrument — coincidence
  measured over a cache would be coincidence by construction.
- **Naming it `not_judged`** → rejected: the `not_*` family names declared identity facts
  (`not_assessed`, `not_applicable`); this state is an execution fact, and the universal
  precedent names it from the execution (`error`). `execution_error` says whose fact it is.

## References

ADR-0034 (whose §4 this supersedes; every other clause — identity vs transport, pinned
models, platform client, duplicated semantics — remains in force) · ADR-0018 (the
mechanical-derivation invariant, refined here; the cause-per-remedy reading its §2
established) · ADR-0016 (assessor changes are identity — why clause 7 bumps
`drafts-hybrid`) · ADR-0023 §3/§7 (same state, two denominators; equal-coverage
comparability, extended to execution variance) · ADR-0021 (the derived `fail` — the
precedent for outcomes minted by machinery with a recorded origin) · ADR-0009 (why scored
outcomes owe quotes and this state carries none) · Inspect AI's error handling
(per-sample errors, `fail_on_error`, the distribution-shift caveat) · the xUnit
fail/error/skip taxonomy · missing-response treatment in large-scale assessment (omitted /
not reached / not administered; PISA's treatment change moving rankings; nonignorable
missingness) · the context-contamination literature on retrying with failed attempts left
in context · the Ragas NaN failure mode (the counterexample) · `backend/README.md` §*What
repeated runs tell you* (the campaign findings that motivated this).
