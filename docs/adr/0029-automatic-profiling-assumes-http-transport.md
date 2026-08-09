# ADR-0029 — Automatic profiling assumes http(s) transport; other roots stay on the manual path

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Content Profiling

## Context

The `ContentVersionRegistered → ProfileContent` policy is conditioned on the human acceptance
of an adapter version and on nothing else (13-code-qa §3.4 and §5). Its fetcher is not part of
that condition: it is fixed at wiring time, `HttpPackageFetcher`, chosen once for every event
the policy will ever see.

Two of the four paths that create contents mint locators that are not URLs. The seeder roots
its frozen packages at the bare course slug (`introduction-to-generative-ai/learn.json`),
resolved later against a fixture directory; `import-learnpack --base-dir` takes its locators
verbatim from a hand-composed JSON, filesystem-relative by design. The other two — the mount
that serves `courses/` and an http package source — mint absolute URLs. Until now the mismatch
was invisible, because the policy was only ever subscribed in the API process, where every
locator is a URL.

That process asymmetry was itself an accident. It was recorded as a decision — "the other
policies stay API-side; seed-demo profiles explicitly, so CLI registration never depended on
them" — and it was true when written, two days before ADR-0027 made `register-package
--source|--all` the bulk intake path in the CLI and re-pointed the seeder through it. The
rationale went stale and the wiring never followed. Repairing it (one subscription list for
every process) exposes the transport mismatch to a policy that has no way to survive it: an
unreachable fetch is not an error in `ProfileContent`, it is a **committed `failed` profile**,
and the policy's own replay guard then refuses those coordinates in either state. A package
that is perfectly readable would be permanently marked broken by the one path that could not
read it.

## Decision

**The automatic path fetches over http(s) and only over http(s); everything else is the manual
path's business.**

1. **One subscription list, every process.** `register_all_policies` is called by the API and
   by the CLI. A guard chain that depends on which process registered a content is not a
   decision anyone took: it is drift the dispatcher cannot detect, because a missing
   subscription looks exactly like an event nobody cares about.
2. **Fourth guard: every artifact locator of the package must be an `http://` or `https://`
   URL.** It is checked before any I/O and **after** the three existing guards (an adapter
   exists · the extraction is accepted · the coordinates are unprofiled), which are cheaper
   lookups — before a team accepts an extraction, guard two declines every event and the
   package read is never paid for.
3. **Declining is a no-op, never a failure.** No profile row, no event. It has to be: letting
   the fetch run would commit a `failed` profile, and guard three refuses existing coordinates
   in **either** state, so that row would be **sticky** over a package that is fine. A `failed`
   profile asserts "the adapter looked and the package was broken" (ADR-0009 §4); here the
   adapter never looked.
4. **Zero artifacts is not a decline.** The guard quantifies over the artifacts, so an empty
   package passes it vacuously — it has nothing to reach, and profiles into all-`absent`
   entries without touching the network. That behaviour predates this ADR and is preserved
   deliberately, not by accident.
5. **The manual path is unrestricted and remains the answer for filesystem roots.**
   `profile-content --base-dir`, `reprofile --base-dir` and the seeder's explicit step choose
   their own fetcher. Automatic and manual differ in transport reach and never in the
   extraction they produce — the adapter cannot tell them apart, which is the point.
6. **Exit condition, recorded so the guard can die.** It exists only because the fetcher is
   chosen at wiring time. When the fetcher is resolved from the package's own root — the shape
   ADR-0027 §1 already gave the registry, where transport is an injected axis — this guard is
   **deleted, not generalized**.

**Deferred, doors left open:** resolving the fetcher from the package root (clause 6); and a
`--no-profile` escape hatch for bulk registration, whose absence is a real cost (below).

## Consequences

- (+) `register-package`, `register-by-source` and the admin form now behave identically.
  ADR-0027's bulk intake finally reaches the profiling step the design always gave it, and the
  answer to "is this course profiled?" stops depending on which door it came through.
- (+) Declining costs one read on a session that is already open — strictly cheaper than the
  round trip, the two inserts and the commit it prevents.
- (+) The acceptance stays the only *human* gate. This guard is about reach, not trust: it can
  never profile something the team has not accepted, and never refuses something on the
  grounds of who registered it.
- (−) A class of content — the seeder's fixtures, `--base-dir` batches — never auto-profiles,
  and the system does not say so at the point of registration. Only the CLI's summary line
  reports it, and only for `register-package`.
- (−) `register-package --all` gets materially slower: roughly one fetch per lesson plus two,
  sequentially, per **created** course, inside that registration's post-commit dispatch. A
  large tree moves from seconds to minutes, and there is no way to opt out.
- (−) The guard is transport-shaped, and so is its blind spot: an http locator that 404s passes
  it and produces a real `failed` profile. The CLI's mount preflight already refuses that case
  before registering; the API path has no equivalent.

## Alternatives considered

- **Resolve the fetcher from the package root (a profiling-side `PackageRoot`)** → deferred,
  not rejected on merit; clause 6 names it as the exit. Rejected *now* because it would have
  to hand the automatic path a base directory it has no business knowing: `DEMO_PACKAGES_DIR`
  is a seeder fixture path and `--base-dir` is a CLI argument. The policy would need the
  operator's filesystem to profile what the operator profiles in one command.
- **Let the fetch fail and keep the `failed` row** → rejected: the row would be a lie about a
  readable package, and a sticky one (clause 3). The manual path can replace it, but only
  after someone notices.
- **Try the fetch and swallow the `ExtractionError` inside the policy** → rejected: it moves a
  cheap declarative guard into the committed path and pays one network round trip per
  registration, in a batch loop, for contents that can never succeed.
- **`any` instead of `all`** → rejected: mixed packages do not exist, because a root mints one
  locator shape for all its artifacts — and `any` would decline the artifact-less package that
  profiles today (clause 4).
- **Gate on the package format, or on which command registered the content** → rejected: the
  format says nothing about transport (the same `LearnpackV1` course is http from `courses/`
  and relative from the fixtures), and the event carries the fact, not the actor. A policy that
  asks who registered something is not a policy.
- **Keep the CLI wired with its own policy set** → rejected: that is the defect. "Registering
  through the form profiles it, registering through the CLI does not" is a rule no design
  states and no reader can predict.

## References

ADR-0003 (post-commit dispatch, replay idempotence, the swallowed handler) · ADR-0009 §4 (what
a `failed` profile asserts) · ADR-0012 (the acceptance is the human gate — guard two) ·
ADR-0022 (soft versus hard failure, the contrast this borrows) · ADR-0027 §1 (`PackageRoot`:
transport as a separate, injected axis — the shape clause 6 points at) and §5 (the `courses/`
mount) · ADR-0028 (locators are transport, not deployment) · 13-code-qa §3.4 and §5 (the guard
chain and the policy table — frozen snapshots that enumerate three guards, not four) · STATUS.
