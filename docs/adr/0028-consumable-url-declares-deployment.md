# ADR-0028 — A consumable URL declares a deployment, not a way to reach the bytes

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

`contents.consumable_url` has been required and http(s)-validated since slice 1, for a reason
that still holds: a human evaluator has to be able to open the course they are scoring.
07-define states it as an invariant of `EducationalContent`, and the whole human path reads it
without ever asking whether it is there — the assignment detail carries it, the evaluator screen
frames it in an iframe, the admin console links it.

ADR-0027 §5 satisfied that invariant for local courses by minting the URL from the dev static
mount. Half of that arrangement is true. The **locators** are honest: they resolve, the brief
intake and the extraction adapter fetch through them, and automated evaluation runs on what they
return. The **consumable URL** is not: `StaticFiles` does not serve directories, so the minted URL
404s — and with a directory listing turned on, what an evaluator would open is a file browser, not
a running course. The invariant was satisfied in shape and violated in meaning, and the failure is
invisible until a human clicks the link during the one activity where the system asks for careful
judgment.

Underneath sits a confusion between two different questions. **Where a package's bytes are** is
transport: per artifact, already carried by the artifact locators, answerable mechanically from
any serving root (ADR-0027 §1). **Whether a deployed, human-consumable instance of this content
exists** is a fact about the world outside this system, and no discovery can produce it — a
package dropped into a folder has no answer to give. The genetic-algorithm loop makes that the
common case rather than the exception: populations are registered in bulk, profiled and scored
automatically, and most of what they generate will never be deployed anywhere. Requiring a URL of
them buys either a minted lie or a refusal to register an evaluand the automated path could score
perfectly.

## Decision

**A consumable URL is an optional declaration that a deployed, human-consumable instance of this
content version exists. A serving root is not a deployment.**

1. **Optional, still http(s) when declared.** Nullable in the domain, in `contents` and across the
   read contracts. The http(s) rule is unchanged and applies to every declared value: `null` says
   "none declared", while `""` and `ftp://…` remain refusals. Null is not a way to smuggle a
   non-URL past the invariant, and a blank is never coerced into a null — a caller that means
   "none" says so.
2. **A filesystem package root never yields one.** The inference from an http-looking
   `locator_base` is deleted: serving a package's bytes, over the dev mount or anything else, is a
   transport arrangement. `HttpPackageRoot` keeps declaring its base URL — for a LearnPack package
   the served root *is* the running course, the one case where transport and deployment coincide.
3. **`RegisterPackageFromSource` stops refusing a source that yields no URL.** The optional command
   field stops being an *override of a discovered value* and becomes a *declaration* — which is
   what the seeder has always used it for, registering frozen demo packages against their real
   `learn-pack.com` deployments.
4. **Automated evaluation is untouched; the human path degrades explicitly.** The `ContentProfile`
   is built from artifact locators (ADR-0009), never from this field, so profiling, assessors,
   studies and the fitness projection do not notice. Human evaluation is what a missing
   declaration blocks, and the console says so: the admin form marks a content that declares no
   deployment when composing a campaign and refuses it in the assign picker, and the evaluator
   screen states the absence instead of framing nothing.
5. **The guard is advisory, not enforced.** Nothing on the server refuses the assignment. Enforcing
   it means Orchestration reading the registry inside the assignment path — a port and a gateway,
   the ADR-0006 shape — and the failure it prevents is visible, reversible and rare: the evaluator
   reads "no deployed instance" and the admin unassigns. Deferred deliberately, recorded in STATUS.
6. **The rows the mount minted are corrected, not left to rot.** Migration 0015 nulls exactly the
   values pointing into a local dev mount (host `localhost`/`127.0.0.1`/`[::1]`, `/packages/` in
   the path); every other value is a real declaration and is preserved. Re-registering does not
   repair them — an unchanged package is a reported no-op (ADR-0027 §4), so without the backfill a
   minted URL would survive forever. A row that lies about being consumable is worse than one that
   declares nothing.

**Deferred, doors left open:** the enforced guard of clause 5 (a registry port in Orchestration
refusing the assignment); and declaring a consumable URL **after** registration, for a course
deployed later — the act has a shape already, `attribute-generator`'s (ADR-0024 §4), and no demand
yet.

## Relationship with ADR-0027

**Amends ADR-0027 §5 in part; it does not supersede it.** What dies is one clause of one sentence:
local contents get honest locators from the mount, *not* an honest `consumable_url` — the mount
never had one to give. Everything else ADR-0027 decided stands and is realized in code: discovery
behind a port, the per-format ACL as the sole writer of the `kind` vocabulary, hard-failing
discovery, content identity by hash, the `courses/` tree and the folder convention. ADR-0027 keeps
its `accepted` status: marking it superseded would retire six live clauses to correct one.

## Consequences

- (+) The field means one thing again, and the meaning is checkable: a value asserts a deployment,
  an absence asserts none. Nothing minted, nothing inferred.
- (+) Local and generated courses become registrable evaluands without a fiction — ADR-0027's
  bottleneck (bulk registration for the genetic-algorithm loop) closes honestly instead of by
  satisfying a validator.
- (+) Subtractive where it was lying and inert everywhere else: the seeder's declarations and every
  package registered from a real http source are unaffected.
- (−) A human evaluator can still be assigned a course they cannot open (clause 5). The console
  prevents it, the server does not.
- (−) **The rule is transport-shaped, not deployment-shaped.** An http root that merely serves a
  package's bytes — a bare file server, a CDN copy — still declares a "consumable" URL that is only
  a file listing. It is the same defect as the mount, one hop away. Accepted because in the
  LearnPack world http-serving a package root *is* how a course is deployed, and a wrong one can be
  overridden by declaring the right one.
- (−) Rows registered before this ADR from a local mount lose a value that at least pointed
  somewhere, and — the repair act being deferred — a course deployed after its version was
  registered cannot declare its URL without a new version or a hand-written update.

## Alternatives considered

- **Serve a directory index (`html=True` on the mount) so the URL opens something** → rejected: it
  makes the URL *resolve* without making it *consumable*. The evaluator would score a course by
  browsing raw READMEs, and the invariant would be satisfied by a file listing. It also widens a
  mount that the ADR-0008 gate exists to keep narrow.
- **Keep the field required and force `--consumable-url` per course** → rejected: it prices in a
  lie at the exact moment nobody has a truth to state, and the batch path (`--all`, the loop's own
  path) has no per-course value to pass.
- **Keep the mount URL and treat it as "consumable enough"** → rejected: that is the status quo,
  and it 404s. "Enough" means a broken link in front of a human being asked to judge.
- **ADR-0024's shape (a required key with a nullable value)** → rejected *for this field*: there,
  silence destroyed the accumulation key of the whole system and was unrecoverable. Here silence
  means "none declared", the state is visible in the console, and the cost of getting it wrong is
  an empty panel. A gate whose absence costs nothing is ceremony.
- **Backfill by structure — null it when the row's artifact locators sit under its
  `consumable_url`** → rejected, and recorded because it looks more precise than the
  host-anchored predicate: that is also the shape of a legitimately http-registered package, whose
  locators `HttpPackageRoot` mints under exactly that base. The criterion would null real
  deployments.
- **Drop the field and let the evaluator open the course from an artifact locator** → rejected: the
  artifacts are the package's insides (ADR-0017 is about evidence); the deployed course is a
  different thing, sometimes at a different host.

## References

ADR-0027 §5 (the amended clause) and §1/§4 (locators and hash identity, both untouched) ·
ADR-0017 (the declared surface is the package — the artifacts, not this URL) · ADR-0009 (why
automated evaluation does not notice) · ADR-0024 (the shape of a declaration, and of a later
repair act) · ADR-0008 (the gate on the dev mount) · ADR-0006 (the port shape the deferred guard
would take) · ADR-0005 (declarative versioning — why a later deployment has no way back today) ·
07-define §`EducationalContent` invariants and 08-code §8 (frozen snapshots this ADR contradicts:
`consumableUrl` is no longer "present") · GLOSSARY (`ContentPackage`) · STATUS (package intake;
the two deferrals).
