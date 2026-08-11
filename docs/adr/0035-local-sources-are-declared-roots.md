# ADR-0035 — Local sources are declared roots, browsed and registered behind a dev-only surface

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

ADR-0027 §5 gave local packages an intake: a gitignored `courses/` tree, one folder per
generator version, a dev-only static mount that serves it so the registered locators resolve,
and a CLI (`register-package`, `--all`) that walks it. It works, and it is the wrong surface for
the loop that now dominates development.

Measuring a generator means registering a batch of freshly produced runs, repeatedly, against a
store that already holds earlier ones. The three questions that decide what to do are all asked
*before* registering: which of these folders is already in the store, which of them changed
since the last run, and which ones are worth registering at all. The CLI answers each of them
only by attempting the write and reading the error — one course at a time, after the fact. The
admin console, which answers every other "what is in the store" question, cannot answer this one
at all: it has no way to see a folder.

Three facts constrain anything built to fix that.

1. **A browser cannot hand the server a filesystem path.** `webkitdirectory` yields bytes with
   relative names, not a path the server can open. Registering those bytes means storing them,
   which is the `PackageStoragePort` stage ADR-0027 deferred with its own ADR. So the picker
   must be server-side: the backend lists directories and the UI navigates them.
2. **Registered locators are permanent and must stay fetchable.** They are what the brief intake
   (ADR-0022) and profiling (ADR-0029) read, and they are written into rows that are never
   rewritten. The mount is what makes local ones honest — and it serves exactly one tree.
   ADR-0028's own rejected alternatives argue against widening it: "it widens a mount that the
   ADR-0008 gate exists to keep narrow." Any folder outside `courses/` therefore has no honest
   registration available today, and registering it anyway degrades into absent briefs and
   failed profiles — silently, which is precisely what the CLI's mount preflight exists to
   prevent.
3. **Discovery fetches paths the package declares about itself.** `.learn/config.json` names the
   exercise files; `files/lesson_plan.json` names the lessons. `FilesystemFetcher` resolves those
   names against a base directory with no containment check. Under the CLI that was tolerable
   because the operator authored `courses/`. A surface that points at arbitrary trees changes
   who wrote the paths being fetched.

Facts 1 and 2 pull against each other: the first says the operator must be able to name any
folder, the second says only a served tree can be registered honestly. Fact 3 says that widening
the reach without widening the guard is how a package gets to name a file outside itself.

## Decision

**Local sources are a declared, finite set of serving roots. A dev-only, admin-only surface
browses them, previews what registering would do, and registers one folder at a time — and the
reach of discovery is bounded by the root, twice.**

1. **Roots are declared, never discovered.** `LOCAL_SOURCE_ROOTS` carries `key=path` entries.
   The repo's `courses/` is always present as the built-in root `courses`, and it keeps serving
   at `/packages` with its base URL unchanged: locators registered before this ADR point there
   and cannot be rewritten. Every other root serves at `/sources/{key}` — a prefix disjoint from
   `/packages`, so no key can shadow a folder and no mount depends on registration order.
   `LOCAL_SOURCES_BASE_URL` states the extras' base URL; it is never derived from the built-in
   one.

2. **A malformed declaration refuses to boot; a missing directory does not.** A duplicate key,
   the reserved key `courses`, a key outside `[a-z0-9._-]+` or an entry without `=` is a
   declaration nobody can act on, and is refused where `AUTH_MODE` is already validated
   (ADR-0008) — gated on local mode, so a leftover variable can never break a real deploy. A
   configured directory that does not exist is an environment fact, not a declaration error: it
   warns, it is skipped, and the surface reports it as absent. Same reasoning as the existing
   `COURSES_DIR.is_dir()` guard, which keeps a course-less checkout booting.

3. **Dev-only first, admin-only second.** The endpoints live in their own router under
   `/dev/local-courses`, and the local-mode gate is declared **on the router**, so it is resolved
   before the admin dependency: outside local mode every path answers 404 rather than 401, and
   the guard is stated once instead of once per handler. The existing `/dev` router stays what it
   is — identities for the sign-in screen, unauthenticated by necessity; this one writes content
   and requires an admin.

4. **The preview is a first-class step, and it is only a preview.** `scan` reports, per immediate
   subfolder, what registering *would* do: `new`, `new_version`, `unchanged`, `conflict` or
   `unreadable` — the five outcomes `RegisterContentVersion` can produce, derived from the same
   hash and identity rules. It writes nothing, and it is never trusted: `register` re-discovers
   and re-derives everything. A scan that has gone stale can only be wrong about a row's label,
   never about what gets written.

5. **Registration takes one folder per request; batch stays a loop in the caller.** ADR-0027 §3
   already made batch a loop over one use case, and the reason is now operational as well as
   architectural: every created course auto-profiles inside its own request (ADR-0029), so a
   whole-tree request would be a multi-minute write with no progress and no bounded failure.

6. **The mount probe binds the write, it does not merely inform the client.** Before registering,
   one real fetch through the minted locator confirms the bytes are served; a failure refuses the
   registration. A preflight that only advises a client it cannot control is ADR-0028's failure
   shape — an invariant satisfied in form and violated in meaning — and the locators it would
   write are permanent.

7. **Containment is enforced at both ends.** The operator's path is resolved and checked to fall
   under its root, and `FilesystemFetcher` refuses any locator that escapes its base directory.
   The first guards what the human named; the second guards what the package named about itself
   (fact 3). Neither substitutes for the other.

8. **Declarations come from the request; the folder convention stays the CLI's.** Format,
   generator version and content version are declared once and apply to every folder in the
   scan. `<name>@<version>/` keeps meaning what ADR-0027 §5 says it means, for the CLI, and this
   surface never reads it — but like the CLI it never mints a generator identity either
   (ADR-0024): an unregistered generator version is refused, not created.

9. **An `unchanged` registration cannot repair a generator, and says so.** The hash match returns
   the existing content untouched, so a declared generator is silently discarded. The surface
   reports that the existing content's generator is unknown and points at the attribution act
   that exists for it (ADR-0024 §4). It never attributes on its own: attribution is an explicit,
   one-way human act, and inferring it from a re-scan is exactly the silence ADR-0024 legislated
   against.

**Deferred, doors left open:** zip upload and stored packages (still ADR-0027's stage 2, and the
only thing that would let a browser register bytes it holds); roots added at runtime instead of
at boot; caching a `DiscoveredPackage` between scan and register; a `--root` flag bringing the
CLI onto the same roots.

## Consequences

- (+) The three questions that decide a batch — already there, changed, or new — are answered
  before anything is written, in the console that answers every other question about the store.
- (+) Generated runs stop having to be moved into `courses/` to be registrable. Where they live
  becomes a declaration in the environment rather than a copy on disk.
- (+) `RegisterPackageFromSource`, `RegisterContentVersion`, the brief intake and the profiling
  policy are untouched: this is a new caller, not a new intake path. Parity with the CLI is a
  property of that, not something to maintain.
- (+) The traversal guard on `FilesystemFetcher` closes a hole that predates this ADR and applies
  to every caller, including the fixtures and the seeder.
- (−) Adding a root needs an environment change and a restart. A dev affordance keeps an
  operational step, which is the price of every registered locator staying fetchable.
- (−) The same package is discovered twice — hashed once by `scan`, again by `register`. Caching
  it between requests would be server state for a dev-only feature, and the second read is the
  one that must be authoritative anyway (clause 4).
- (−) Two URL shapes exist for the same kind of thing, `/packages` and `/sources/{key}`, and the
  asymmetry is permanent. It buys never invalidating a stored locator.
- (−) A registered local course still declares no consumable URL (ADR-0028): a served root is
  not a deployment, so these courses remain automatically evaluable and not humanly assignable.

## Alternatives considered

- **Nest the extra roots under `/packages/{key}`** → rejected: Starlette matches mounts by
  prefix, so correctness would depend on registration order in the composition root — an
  untested coupling — and a root keyed `unknown` would shadow the real `courses/unknown/`
  folder, serving the wrong bytes without an error.
- **Derive the extras' base URL from `local_packages_base_url`** → rejected: any derivation
  ("replace the last segment") breaks under a proxy path prefix, and the failure is a dead
  locator written into a row that is never rewritten. Two settings can drift; the probe of
  clause 6 is what detects drift, and it is cheap.
- **Symlink external trees into `courses/` and change nothing** → rejected: `StaticFiles`
  refuses to follow a symlink out of its directory while `FilesystemFetcher` follows it happily,
  so discovery would succeed and every locator it minted would 404 — fact 2's silent failure,
  reproduced exactly.
- **Accept any absolute path the server can read, with no allowlist** → rejected twice over: it
  serves the operator's disk over http, and it registers locators the mount cannot serve. The
  allowlist is not primarily a security boundary on a dev box; it is what makes a locator honest.
- **One request that registers the whole selection** → rejected: see clause 5. It also forces a
  partial-failure aggregate and a session per folder, to buy a loop the caller can already write.
- **Auto-attribute the declared generator when the outcome is `unchanged`** → rejected by
  ADR-0024, and it is the tempting repair: the operator is looking at the course, has just named
  a generator, and nothing happens. Clause 9 makes the act available without making it implicit.
- **Put the endpoints in the existing `/dev` router, or in the registry's admin router behind an
  inline gate** → rejected: the first has a different contract (unauthenticated, for sign-in) and
  the second mixes admin-gated with admin-and-local-gated handlers in one 500-line file, which is
  how a gate gets forgotten. Clause 3's router-level dependency also fixes the 401-before-404
  leak an inline check would leave.
- **Refactor the CLI onto the shared root resolution** → rejected as churn: it would rewrite a
  fixture and several tests that monkeypatch `cli.COURSES_DIR` to delete a dozen lines, for a
  command whose contract is deliberately `courses/`-only. One assertion pins that both mint the
  same locator; the refactor becomes worthwhile only if the CLI grows `--root`.

## References

ADR-0027 §5 (local sources, the `courses/` tree and the folder convention this surface leaves to
the CLI) and §3 (batch is a loop over one use case) · ADR-0028 (a served root is not a
deployment, and the "widens a mount the ADR-0008 gate keeps narrow" objection this ADR answers
with declared roots) · ADR-0008 (local mode: the gate, and where a malformed declaration is
refused) · ADR-0024 (explicit generator attribution — clauses 8 and 9) · ADR-0022 (brief intake
fetches the locators, which is why they must resolve) · ADR-0029 (automatic profiling assumes
http transport — why registration is slow and takes one folder) · ADR-0005 (declarative
versioning — the `new_version` and `conflict` verdicts) · ADR-0017 (the declared surface is the
package) · `courses/README.md` · `backend/README.md` §*Registering courses*.
