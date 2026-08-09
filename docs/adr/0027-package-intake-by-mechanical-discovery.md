# ADR-0027 — Package intake by mechanical discovery behind a port

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

Design 11-connect names two ACL edges: intake (registry, "mechanical, thin") and extraction
(profiling, interpretive). The extraction edge is mature — a versioned, capability-declaring
adapter over fixture packages, gated by a human `ExtractionAccepted` act (ADR-0012). The
intake edge was never built: registering a content version means a human typing
`{kind, locator}` artifact rows into the admin form, or hand-writing them in a JSON file for
the CLI. The only mechanical enumeration of a package's artifacts in the codebase is a
seeder helper hardwired to the test fixtures.

The consequences compound. The artifact `kind` vocabulary has no owner — it is written
free-hand at registration and read by an extraction adapter that has learned not to trust it
(its `_lesson_slug` validates structurally because a mislabeled asset once invented a
phantom lesson). Five registration entry points carry three mutually incompatible input
shapes. Nothing ties the registered locators to what the package actually contains, and
nothing detects that the bytes behind a registered version changed. Local packages cannot be
registered at all — every locator must be typed, and `consumable_url` must be http(s) —
while STATUS records bulk registration as the first bottleneck for the genetic-algorithm
loop and decides "register by link" as stage 1 of the package-intake plan.

The industry's ingestion patterns (promptfoo, OpenAI Evals, SCORM on the file side;
Braintrust, Langfuse, Weave on the platform side) converge on: a manifest plus a directory
convention replaces registration forms; push and pull sources resolve into one normalized
registration; content hashes make re-ingestion idempotent. LearnpackV1 supports this
mechanically: `.learn/config.json` enumerates every exercise's files (lesson bodies via
`translations`, code files via `files[]`), so the full artifact list is derivable without
walking directories — the same reading works over the filesystem and over HTTP.

## Decision

**The registry discovers a package's declared surface mechanically, behind a port; humans
declare a source, never an artifact list.**

1. **Where:** a `PackageDiscoveryPort` in the registry's application layer —
   `discover(package_format, source_locator) → DiscoveredPackage` (descriptor, artifact
   list, content hash) — realized by a **per-format discovery ACL registry**
   (`DISCOVERIES_BY_FORMAT`, the ADR-0022 pattern). For `LearnpackV1`, discovery reads
   `learn.json` (identity + descriptor), `.learn/package-manifest.json`, and
   `.learn/config.json` (the exercise enumeration), and includes
   `.learn/initialSyllabus.json` when present. Transport is a separate axis: a `PackageRoot`
   (filesystem or HTTP) is injected, so one discovery works over any serving root.
2. **Discovery is the sole writer of the artifact `kind` vocabulary** (`manifest`,
   `package_manifest`, `syllabus`, `lesson_content`, `lesson_file`), aligned with what the
   extraction adapter and the brief intake read, and pinned by a test. The extraction
   adapter's structural defenses remain — defense in depth, no longer the only line.
3. **Single canonical registration path:** discovery produces a
   `RegisterContentVersionCommand`; `RegisterContentVersion` remains the only writer of
   `contents`. Discovery is **hard-failing** — a package whose manifest or enumeration
   cannot be read is not registered. This deliberately contrasts with the brief intake's
   soft failure (ADR-0022 §4): an absent brief is a recorded state of a valid evaluand,
   while a mis-discovered package would *be* the evaluand, wrong.
4. **Content identity by content:** discovery hashes the fetched artifact bytes —
   `sha256` over `path:sha256(bytes)` lines sorted by root-relative path, so the same
   package hashes identically from any serving root — and registration stores it in
   `contents.content_hash` (nullable; hand-registered rows carry none). Re-registering the
   same `(package_format, external_id)` with an identical hash is a reported no-op; the same
   declared version with a different hash is refused ("the content changed but the version
   did not — declare a new version"). Versions stay declarative (ADR-0005); the hash makes
   drift visible instead of silent.
5. **Local sources:** a gitignored `courses/` directory at the repo root, one folder per
   generator version (`<name>@<version>`, or `unknown` for contents whose generator is
   declared unknown per ADR-0024), courses inside. A dev-only static mount (gated like the
   rest of the local surface, ADR-0008) serves it over http(s), so locally registered
   contents get honest locators and `consumable_url` without touching the domain invariant.
   The folder-name convention is provisional and isolated in one resolution function; a
   folder naming an unregistered generator version aborts the import — mechanical intake
   never mints generator identities.
6. **The slice-1 seam retires:** `acl_learnpack.to_register_command` and the CLI's `--acl`
   path — built for a payload shape nobody produces — are deleted. `derive_brief` stays:
   ADR-0022 is live and untouched; discovery feeds it better (the syllabus artifact is now
   found mechanically).

**Deferred, doors left open:** zip upload with a `PackageStoragePort` (STATUS stage 2, its
own ADR); pull-based batch registration from the LearnPack API (`[future]` connected ACL — a
new root/source for the same port and the same loop); automatic re-versioning when the hash
changes (today: refusal with a clear message); richer generator-folder conventions.

## Consequences

- (+) One intake path for form, CLI, seeder and the future GA loop; batch registration of a
  directory of courses is a loop over the same use case.
- (+) The `kind` vocabulary gains a single writer; registration-time labeling bugs stop
  being an input class the extraction adapter must survive.
- (+) Idempotent re-import and detectable content drift, at the cost of one nullable column.
- (+) Local courses become first-class evaluands in dev — the GA loop's first bottleneck
  (bulk registration) is reduced to dropping folders and running one command.
- (−) Registering a local course requires the dev API to be running (locators point into the
  mount); the CLI preflights the mount and refuses loudly rather than degrade into absent
  briefs and failed profiles. An offline fallback (mount-aware fetcher) is noted, not built.
- (−) Discovery fetches every artifact to hash it — heavier than registering locators blind.
  That weight is the point: a package that cannot be fetched whole was never registrable
  evidence.
- (−) `contents` rows created before this ADR have `content_hash = null` and never dedupe by
  content; they keep working (the no-hash path is unchanged).

## Alternatives considered

- **Snapshot the package bytes at registration** → deferred, not rejected: the frozen
  evidence today is the `ContentProfile` (ADR-0009); storage arrives with stage 2
  (`PackageStoragePort`), and the hash already pins what was seen.
- **Soft-failing discovery (register what could be read)** → rejected: a partially
  discovered package silently narrows the declared surface — the exact silence ADR-0024
  legislated against for the generator link. Contrast with ADR-0022, where the absent thing
  is metadata about the evaluand, not the evaluand.
- **Trust `initialSyllabus.json`'s per-lesson `sourceContentHash` as the content identity**
  → rejected: generator-internal, per-lesson, unverifiable; the registry hashes what it
  fetched.
- **Auto-register unknown generator folders** → rejected: ADR-0024 makes the generator link
  an explicit declaration; mechanical intake creating identities would be silence wearing a
  convention.
- **Extend `import-learnpack` instead of a new subcommand** → rejected: its contract is
  "bulk from a canonical JSON file"; grafting a source-based mode onto its already-retired
  `--acl` flag matrix multiplies invalid combinations. The JSON path stays for
  hand-composed batches.

## References

ADR-0017 (the declared surface is the package) · ADR-0022 (mechanical brief intake — the
per-format registry pattern, and the soft/hard contrast) · ADR-0024 (explicit generator
attribution) · ADR-0005 (declarative content versioning) · ADR-0008 (local development
mode gates the mount) · ADR-0009 (extraction without inference — the profile as frozen
evidence) · 11-connect §ACLs — two edges · 13-code §3.4 (per-format adapter registry) ·
STATUS 2026-08-08 (package-intake stages; bulk registration as the GA bottleneck) ·
GLOSSARY (`ContentPackage`, `PackageArtifact`, `PackageFormat`).
