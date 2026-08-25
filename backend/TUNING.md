# Throughput and its ceilings

How much this backend asks for at once, what bounds each of those numbers, and how to tell
which ceiling is the one holding a batch back. Nothing here is needed to run the system — the
defaults are chosen to be safe — and it is worth reading when a batch is slower than you want,
or when it fails in a way nobody named.

Three ceilings, each at a different door:

| Setting | Bounds | Default | Bounded in turn by |
|---|---|---|---|
| `BATCH_MAX_COURSES` | courses evaluated at a time | 6 | the database connection pool |
| `LLM_MAX_CONCURRENCY` | LLM requests in flight, at the transport | 16 | what the account is served |
| `HTTP_MAX_CONCURRENCY` | artifact fetches in flight, at the transport | 8 | somebody else's course server |

The two transport ceilings hold **whatever the callers do**, so nested fan-outs can never
multiply into a burst nobody chose.

## Evaluating a study in batch

**How much it asks for at once — two numbers, not one.** `--concurrency` is how many
**courses** run at a time (default `BATCH_MAX_COURSES`, 6). How many **requests** may be in
flight is `LLM_MAX_CONCURRENCY` (16) at the transport itself, whatever the callers do, so
nested fan-outs can never multiply into a burst nobody chose.

They are configured apart because one course is no longer one request. An evaluation looks at
every judgeable criterion at once (ADR-0048), and `drafts-hybrid` asks its concept map as one
call plus one per module inside that — so one course peaks at roughly
`(1 + modules) + judged criteria + single-call tasks`, which is sixteen on the drafts measured.
Requests wanted is that times the courses in flight. A ceiling below it does not save anything:
it only moves the wait into the transport's queue, where it is recorded as latency and reads
like a slow model.

`LLM_MAX_CONCURRENCY` is bounded by what the account is served — OpenRouter states no
concurrency limit for paid models and governs capacity per account, so opening more keys buys
nothing. If the endpoint pushes back, the transport backs off on 429 honouring `Retry-After`:
overshooting costs retries, not correctness.

**`BATCH_MAX_COURSES` is bounded by the database instead**, and that is the lever worth
knowing how to move.

```
DB_POOL_SIZE + DB_MAX_OVERFLOW  ≥  2 × workers  +  headroom
```

Two per worker, because a worker holds its own session and the one the policy opens when the
evaluation commits — a policy runs in its own transaction (ADR-0003). At the defaults that is
`5 + 10 = 15`, which serves seven workers with one connection left. Six is the default rather
than seven on purpose: a pool that runs out does not make a batch slower, it makes a checkout
wait `pool_timeout` and then raise, and **a failure nobody named ends the whole batch** rather
than one course.

**To run bigger batches**, raise the two together — `BATCH_MAX_COURSES` and the pool, in the
same change — and check the server's own limit before you do: the local Postgres serves 100
connections and a managed one has its own, so a pool above it just moves the error. Then
measure, because the point is throughput and not the setting:

- **Did it help?** Compare the batch's wall clock against the sum of the per-course durations
  the summary reports. Six courses at four at a time is 304 s against 963 s; the same six all
  at once is 180 s against 954 s. Once the wall clock equals the slowest single course, more
  workers buy nothing — that is the floor for that set.
- **Did it cost anything?** Read the map's tokens per second in the run's trace. Across both
  of those batches it stayed at 97–141, the same band one course produces alone, which is how
  you know the requests ceiling is not what is holding the batch back. If it falls, the next
  limit is `LLM_MAX_CONCURRENCY` or the account behind it, not the pool.
- **What failure looks like:** courses ending with a cause nobody named, and the batch
  stopping instead of carrying on. That is the pool, not the endpoint — a rate limit shows up
  as retries and 429s in the trace, and the transport absorbs it.

## Registering and profiling a package

Measured against real courses with `--from-csv`, a new one costs about **9 s** and one already
registered about **4.6 s**, so fifty is roughly seven minutes of terminal — short enough to sit in
front of, which is half of why that intake runs in the foreground.

**How much a registration asks for at once.** A package's manifests are read one at a time,
because each one names the next; everything they then enumerate — dozens of lesson bodies and
exercise files, 73 on the course measured — is asked for **together**, since nothing in that
list is opened to find another. Over http that is a fan-out; off a filesystem it is still a
loop, because a local read has nothing to wait for.

`HTTP_MAX_CONCURRENCY` (8) is what bounds it, at the transport, so it holds for every artifact
fetch whoever asked for it — a discovery reading a package and a profiling run reading another
are the same requests to whoever is serving them. It is deliberately lower than
`LLM_MAX_CONCURRENCY`, and not because origins are weaker: there the account is ours and the
transport backs off on 429 honouring `Retry-After`, so overshooting costs retries. Here the
origin is somebody else's course server, and a fetch that runs out of attempts refuses the
whole registration (ADR-0027).

**It does back off**, on the same policy: a connection error, a timeout or a `429/5xx` is the
origin's weather, so it is retried up to three attempts with a jittered backoff that honours
`Retry-After`. Every other 4xx is a fact about what was asked for, and re-asking cannot change
it — so it is answered at once and never waited on. That case is not an edge: a package saying
it carries no syllabus is a **404 read on every registration** (ADR-0022), and making it wait
would tax every package that is fine. Note that origins differ in how they say it —
`learn-pack.com` answers **403** for a missing artifact, not 404 — which is why the rule is
"retry the retryable list", not "retry everything except 404".

**What failure looks like now**: a course that used to register and now does not, with a
message naming one artifact and `(after 3 attempts)`. That suffix is the tell — with it, the
origin refused three times and the ceiling may be too high for it; without it, the origin
answered, and the package really is missing that artifact.

**What it measures, on a real course** (39 artifacts on `learn-pack.com`, about half a second a
request): reading the declared surface takes **19.6 s one file at a time and 4.4 s at the
default ceiling of eight** — 6.4 s at four, 3.2 s at sixteen, 3.1 s at twenty-four, no failure
at any of them. Flat past sixteen, because what is left by then is the part that cannot fan out
at all: three manifests read one after the next, since each one names the next. To try a
different ceiling on your own origin, measure the same way and read both things — the wall
clock, and whether any artifact started failing.

**Profiling reads the same way, for the same reason.** It re-reads the package right after
discovery, inside the same registration (ADR-0029), and its two group reads — the lesson
bodies, and LearnpackV2's stats files — go out together as well: **9.4 s → 2.3 s** on that
course, with the extraction returning byte-identical entries.

It also reads each artifact **once**. An adapter's entry builders are independent on purpose,
each reading and citing its own artifact without consulting the others, so the same file is
legitimately asked for more than once — LearnpackV2's `lesson_plan.json` three times. Rather
than couple the builders, `ProfileContent` wraps the fetcher for the length of one extraction.

**So a whole registration is about 8 s of work against the ~31 s it started at**, and when
timing one, the two halves are still worth timing apart: the CLI's `created …` line closes the
discovery, and what `register-package` prints after it is the profiling.

## Where to look next

- `README.md` — the commands these numbers apply to
  ([registering courses](README.md#registering-courses),
  [evaluating a study in batch](README.md#evaluating-a-study-in-batch)).
- ADR-0040 — why a batch is a run, and why it refuses before it spends.
- ADR-0027 — why a failed artifact fetch refuses the whole registration.
