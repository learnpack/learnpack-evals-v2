# ADR-0040 — A batch is a run: one ceiling on concurrency, one way to stop, and the course as the unit

**Status:** accepted · **Date:** 2026-08 · **DDD context:** composition root · Evaluation

## Context

A generation of the optimization experiment is a study's worth of courses. One course is
about sixteen LLM calls today and will be forty once the criteria that read every lesson
exist, so twenty courses is three hundred calls now and eight hundred later. Nothing in the
system runs any of it concurrently: the derivation walks criteria in a `for` loop and the
transport is synchronous, which makes a generation a matter of hours.

Three facts constrain what may be done about that.

1. **The endpoint's limit is not ours to know.** OpenRouter's rate limit is account-scoped
   and changes; a number hardcoded here would be wrong somewhere. The transport already
   survives being over the limit — it backs off on 429 honouring `Retry-After` — but nothing
   stops a caller from *asking* for far more than the account allows, and the cost of having
   asked is not recoverable by backing off.
2. **Concurrency will nest.** The pending lesson-level criteria are a fan-out *inside* a
   course: map over lessons, pairs or modules, reduce in code. A batch over courses and a
   fan-out over lessons multiply, and no cap set per level bounds their product.
3. **The work is long and expensive, so it must be stoppable** — and stopping has to be
   honoured soon rather than after the fifteen calls already queued.

There is also a defect that only concurrency makes systematic: `drafts-hybrid` memoizes its
tasks in module-level dicts, emptied at the start of each dry run. Two runs that overlap
empty each other's answers, and over one profile the second can be served the first's — so
two repeats stop being two samples, which is precisely the measurement repeats exist for.

## Decision

**Batch evaluation is a run in the composition root: courses are its unit, the transport is
where concurrency is capped, and cancelling means stop starting.**

1. **One gate, at the transport.** `LLM_MAX_CONCURRENCY` (default 4) bounds requests **in
   flight**, enforced by a semaphore in the shared client. It is the only place that sees
   every call regardless of how many levels of fan-out sit above it, so a caller may nest
   fan-outs freely and the ceiling still holds. The slot is released before any backoff — a
   slot held by a sleeping caller is an idle slot. This is a ceiling, not a rate limiter:
   the reactive half already exists, and what it cannot provide is *not having asked*.

2. **Concurrency is access, not identity (ADR-0034).** It changes whether and when an answer
   arrives, never which one, exactly like the timeout. Making it identity would mean every
   change of throughput re-versions the assessor and discards its calibration, which would
   be expensive and untrue.

3. **The unit is the course.** ADR-0037 decides what happens inside one evaluation; this
   decides what happens between them. A course that fails is one row of the summary and the
   batch continues — with three exceptions that are not this course's problem:
   a **configuration** failure and an `InvalidAutomatedEvaluation` are properties of the
   wiring, identical for every course, so the first one ends the batch; and **three
   consecutive transport deaths** mean the endpoint is gone, so they end it too. Any course
   that completes clears that streak.

4. **What can be refused is refused before anything is paid for.** A study that is not open,
   no pinned instrument, an empty dataset, an unregistered or unratified assessor: each
   would fail identically for every course, and learning it on course nineteen costs
   eighteen courses' worth of money to discover what course one already knew.

5. **Cancelling means stop starting, and nothing is undone.** A token in a `ContextVar` —
   the mechanism the observability sink already uses to cross that boundary — is checked by
   the transport before each request, because a call not issued is money not spent.
   Courses that finished stay finished; the one in flight persists nothing, since an
   evaluation that does not reach its end writes nothing (ADR-0037). `Cancelled` derives
   from `BaseException` for the same reason `KeyboardInterrupt` does: an `except Exception`
   that absorbed it would turn a stopped run into a persisted evaluation full of
   `execution_error` — a record of judgments nobody made.

6. **Re-running resumes.** By default a course this assessor already evaluated under this
   instrument version is skipped, so the answer to a batch that died halfway is to run it
   again. `--re-evaluate` overrides.

7. **Memoization is scoped to one evaluation.** The task caches move from module dicts to
   `ContextVar`s: a thread that never opened a scope gets its own on first use, and an
   explicit scope isolates sequential runs in one thread. Within an evaluation nothing
   changes — criteria sharing a task still share one answer and degrade together (ADR-0037
   §2) — so **no assessor version is bumped**; what disappears is a leak that was never
   intended.

8. **It lives in the composition root** (`app/platform/batch_runs.py`), because it names two
   modules' adapters — the study on one side, the evaluation on the other — which only the
   composition root may do (ARCHITECTURE.md §3). It also keeps the rule that studies never
   command Evaluation: the study is read, not asked.

9. **The run is in memory and the record is in the database.** Progress, steps and the
   estimate live with the run and die with the process; what survives is the evaluations
   themselves, so "how far did it get" is answerable after a restart as a query over
   judgments. The estimate is a **range**, computed from the durations this run has already
   measured, because course durations spread by a factor of two or three and a single figure
   would be a promise the work cannot keep.

## Consequences

- (+) A generation is one command, and its wall-clock drops by roughly the worker count.
- (+) The lesson-level fan-out can be built later without revisiting any of this: it nests,
  and the ceiling is already where it needs to be.
- (+) The memoization fix repairs a present defect — overlapping calibration runs — and is
  what makes concurrent evaluation safe at all.
- (+) A batch that is interrupted, by an operator or by an outage, costs only what it spent.
- (−) The database pool becomes the next limit: the default is 5 + 10 overflow and each
  worker uses up to two sessions, so a concurrency above ~7 needs the pool raised. Named
  here and in the setting rather than discovered as a timeout.
- (−) Failure kinds now carry batch-level meaning (`configuration` is fatal, `transport`
  accumulates). The taxonomy was ADR-0037's, written for another purpose; a kind added
  carelessly later changes when a batch stops.
- (−) A run started from the console cannot be seen or cancelled from the CLI, and neither
  survives a restart. For a local, single-operator tool that is the correct trade.

## `[future]`

- **The console surface**: start, watch and cancel from `/admin/studies`, plus the durable
  progress count. The run object and its use case exist for it; what is missing is a
  registry and three endpoints.
- **Fan-out within a course** for the criteria that read every lesson. Bounded by clause 1
  already; what is left to decide is the queue policy — depth first (finish a course, so a
  trace can be read whole) versus breadth first (start many courses). A semaphore leaves
  that open, which is why it is a semaphore and not a cap per level.
- **Adapting concurrency to observed 429s.** The reactive half absorbs them today, and the
  account's real limit is a measurement nobody has taken yet.

## Alternatives considered

- **A cap per fan-out level** → rejected: it does not compose. Five courses times eight
  lessons asks for forty and nobody decided forty.
- **A rate limiter (requests per second) instead of a ceiling on in-flight requests** →
  rejected for now: it needs the account's real limit, which is exactly what we do not know,
  while a ceiling is safe under any limit and turns into a rate through latency.
- **Making the batch a study command** → rejected: studies never command Evaluation, and a
  use case that named both modules' adapters would break module isolation. The composition
  root is where two modules may be named.
- **Persisting runs in a table** → rejected: the durable facts are the evaluations, which
  are already persisted, and a run table would be a second source of truth for progress.
- **Rolling back a cancelled batch** → rejected as unnecessary: there is nothing partial to
  roll back, and discarding completed evaluations would throw away work that is valid.
- **Cancelling by killing the process** → rejected: it loses the summary, and leaves the
  operator unable to tell what was persisted from what was not.
- **A `Cancelled` deriving from `Exception`** → rejected: the assessor's typed handlers exist
  to convert broken calls into `execution_error`, and a stop is not a failure.
- **Keeping the module-level memoization and serialising runs instead** → rejected: it makes
  a correctness property depend on an operator not doing two things at once, which is how
  the defect got here in the first place.

## References

ADR-0034 (LLM-carrying assessors: identity vs. access — clause 2 applies its rule, and §3's
provider question is untouched) · ADR-0037 (execution failure is an outcome: what happens
INSIDE one evaluation, and the failure-kind taxonomy clause 3 reads) · ADR-0027 §3 (batch is
a loop over one use case, decided for registration and applied here one level up) ·
ADR-0035 §5 (why a multi-minute request with no progress and no bounded failure is the wrong
shape — the reasoning the run form follows) · ADR-0019 (ratification: what clause 4 refuses
early) · ADR-0039 (the brief axis the summary reports per course) · ARCHITECTURE.md §3 and
`tests/test_architecture.py` (why this lives in the composition root) ·
`backend/README.md` §*Evaluating a study in batch*.
