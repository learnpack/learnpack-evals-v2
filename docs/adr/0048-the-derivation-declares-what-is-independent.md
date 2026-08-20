# ADR-0048 — The derivation declares what is independent; the mechanism is injected

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation

## Context

`derive_and_execute` walks an instrument's criteria one at a time. That was free while an
executor was a count over a profile, and it stopped being free when executors started carrying
LLM calls: on the drafts measured, one evaluation is 22 requests and 283 seconds, of which the
concept map is 114 — asked as one call per module, together — and the remaining fifteen are
~120 seconds spent strictly one after the next behind it.

Nothing makes them sequential except the loop. **Each criterion is decided from its own spec,
the profile and the coverage, and none reads another's outcome.** The only cross-criterion
state is the failure count and the metric map, and both are folds over results rather than
inputs to them. The independence is already true; the loop simply does not say so.

**The obvious repair is the wrong one.** Putting a thread pool inside `derivation.py` looks
like four lines, and one of them gives it away: `copy_context()`. A worker thread starts with
an empty context, and what a run carries in `ContextVar`s is what it cannot afford to lose —
the assessor's memoized answers, the trace sink, the cancellation token. All three belong to
layers the domain must not know about (ARCHITECTURE.md §1: the domain is pure Python, no I/O),
and the domain would be copying context for no reason of its own. A line whose entire
justification lives in three infrastructure modules is a line in the wrong file.

There is prior evidence for how quietly that goes wrong. The concept map's own fan-out shipped
without carrying the context and emitted **nothing** to the trace: the most expensive task in
the evaluation left no record of what it asked, the run looked fine, and the trace was merely
short.

So the question is not whether to run criteria together. It is which layer gets to say what.

## Decision

**The derivation declares that its criteria are independent and asks for the answers in order;
how they are produced is injected, and the default is sequential.**

1. **Independence is domain knowledge, and the domain states it.** Causes (a)–(d) are decided
   first, in order and without cost: they read declared facts and nothing else. Only (e) —
   the criteria whose evidence has to be looked at — is handed over.

2. **The mechanism is a collaborator, not a choice made here.** `RunIndependently` is the whole
   contract: *apply this to every item and answer in the same order*. It says nothing about
   threads, processes or time, and an implementation that ignores all three by doing them one
   at a time is a correct one — it is the default (`one_at_a_time`), which keeps this module
   correct, pure and deterministic on its own.

3. **The concurrent implementation lives where what it must carry lives**
   (`app/platform/concurrency.py`), beside the trace sink and the cancellation token it
   propagates. One context copy per item, never one shared: a `Context` cannot be entered from
   two threads at once.

4. **The order is the instrument's, never the order of arrival.** Outcomes, metrics and the
   budget arithmetic are all decided in a second pass over answers that are already in. Two
   runs over the same answers produce the same outcomes and raise out of the same criterion,
   whatever finished first.

5. **The failure budget is applied when every answer is in.** The verdict is unchanged; what is
   lost is the early stop, and that was a side effect rather than the decision — ADR-0037 §3
   decides **what is worth persisting**, not how much a dying run saves. A run past its budget
   now pays for the calls that were already in flight. `InvalidAutomatedEvaluation` still beats
   the budget on the first criterion that exposes it, and `Cancelled` still crosses everything
   without being absorbed (ADR-0037 §1).

6. **Scheduling is not identity.** Nothing about which answer arrives changes: the same
   question, the same corpus, the same sampling. This is ADR-0034 §1's line — *when* an answer
   arrives is access, *which* answer arrives is identity — carried from the transport to the
   order the work is issued in.

7. **The ceiling stays single and stays at the transport.** The domain neither knows nor asks:
   it releases everything judgeable, and one semaphore per process bounds what actually goes
   out. That is what makes the levels compose — a batch over courses, this over criteria, a
   task over modules — where a cap per level would leave nobody having decided their product.

8. **What this asks of an assessor**, stated because it is new in the `Executor` contract: its
   executors must be safe to run at the same time, and a task several criteria share must still
   be asked **once**. The domain does not know which of them share anything. `drafts-hybrid`
   meets the second by claiming a memo entry before the work starts rather than after it
   returns — the same rule it always had, restated for callers that arrive at the same moment.

## Consequences

- (+) **An evaluation goes from 283 to 149 seconds** on the measured draft, with the same
  verdicts, the same map (111 rows against 108 and 109) and no 429 or retry.
- (+) **The domain gains no import it did not have**, and its twenty derivation tests run
  unchanged on the default. What concurrency does is tested where it happens.
- (−) **A dying run costs more.** Past the budget the calls already issued are paid for. On the
  configuration failures that end a batch this is bounded by one evaluation, and it buys the
  property in clause 4.
- (−) **Threads multiply across levels**: a batch of four courses now holds four pools of ~20.
  Threads waiting on a semaphore ask for nothing, and the ceiling is what bounds the requests,
  but the arithmetic is worth knowing before raising the batch's own worker count.
- (−) **Per-call throughput dips when more is in flight**: the map's calls generated at 96–125
  tokens per second against 106–134 with less running. The total is what improved, not the
  individual latency, and the ceiling is the knob if that trade ever stops paying.
- **The peak demand of one course moved**, so `LLM_MAX_CONCURRENCY` moves with it: the map's
  seven now overlap the five judged criteria and the four single-call tasks.

## Alternatives considered

- **A thread pool inside the derivation** → rejected, and it is the one that looks cheapest.
  The `copy_context()` argument above is the whole objection: the domain would carry
  infrastructure's needs, and the next thing it must carry would arrive without anyone noticing
  it had been made responsible.
- **Warming the tasks from the application** — run the executors concurrently before the loop
  so the loop finds every answer memoized → rejected. It either duplicates the (a)–(d)
  precedence outside the domain, so criteria the loop would have skipped get paid for, or runs
  every executor twice. It also hides the scheduling in a place with no claim to decide it: an
  executor call would quietly acquire side effects.
- **Splitting the derivation into pure pieces and orchestrating from the application**
  (plan → execute → assemble) → rejected, and it is the closest call. It leaves the domain not
  calling I/O at all, which is cleaner in the abstract; it also moves out of the domain the
  invariant this module holds by construction — exactly one outcome per criterion of the
  snapshot — and spreads one argument across two layers.
- **Making the whole path async** → rejected as out of proportion: the stack is synchronous end
  to end, and what is needed is a fan-out over a handful of independent units, not a runtime.

## References

ADR-0037 §1 and §3 (execution failure is an outcome; the failure budget — clause 5 keeps its
decision and drops its side effect) · ADR-0034 §1 (semantics are identity, transport is
environment — the line clause 6 extends) · ADR-0016 (the assessor as a versioned artifact, and
the `Executor` contract clause 8 adds to) · ADR-0018 (declared coverage: the abstentions clause
1 resolves without a call) · ADR-0019 (ratification per version — why a missing executor is a
bug rather than an outcome) · ADR-0040 (a batch is a run — the level this one nests inside) ·
ARCHITECTURE.md §1 and §3 (the domain is pure Python; ports are defined in the inner layers and
adapters implemented outside — the shape clauses 2 and 3 follow) · 13-code §3.5 (frozen
snapshot: the derivation as a single sequential pass — amended here) ·
`app/modules/evaluation/domain/derivation.py` and `app/platform/concurrency.py` (the two halves
this decision separates).
