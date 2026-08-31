# Adding a package format

This is the guide for one job: this system knows how to read some packaging conventions
(`LearnpackV1`, `LearnpackV2`) and you have a new one. It assumes you have the repository
running — [`../backend/README.md`](../backend/README.md) is the setup — and it does not
assume you have read the design.

The other side of the same coin is [authoring an instrument](RUNBOOK-authoring-an-instrument.md):
a format teaches the system to *read* something, an instrument decides what is worth *asking*.

Every command below is run from `backend/`, and every path in prose is relative to this
file.

A *package format* is a packaging convention this system knows how to read (e.g.
`LearnpackV1`). Supporting a new one means writing two or three small adapters against
existing ports, plus a handful of recorded human acts. You never touch the domain model,
the evaluation pipeline, the frontend, or the database schema.

**Concepts you need (30 seconds).** A *port* is an interface the core defines
(`FormatPackageDiscoveryPort`, `ExtractionAdapterPort`, `FormatBriefIntakePort`); an
*adapter* is your implementation of it for your format; a *registry* is the dict that maps
format name → adapter — adding a format is one new entry, never a wiring change.
Everything downstream of the `ContentProfile` (the canonical representation your
extraction adapter produces) is format-agnostic and does not change. The steps below land
**incrementally**: after step 2 your packages already register and dedupe; profiling and
evaluation come later.

The contract every format must satisfy is executable:
`backend/tests/test_format_contract.py`, parametrized over `backend/tests/format_cases.py`. A format
registered in any registry without a `FormatCase` fails the suite — so the kit is also
your to-do list: add your case early and work until it is green.

## Step 0 — Choose the format name. Carefully.

The string (e.g. `LearnpackV2`) is the namespace of every `externalId` (ADR-0005) and
travels into immutable rows: persisted profiles, published study reports. There is no
rename. This is the step with the least code and the most consequences.

## Step 1 — Freeze a real fixture package

Copy one real, representative package into `backend/tests/fixtures/<your_format>/`. The fixture
comes first, not last: every later step is verified against it, and the contract kit
requires it. Prefer a package that exercises the format's full surface — every artifact
kind, and the commission if the format carries one (see the `FormatCase` fields).

## Step 2 — Discovery adapter (required; makes the format registrable)

File: `backend/app/modules/evaluand_registry/infrastructure/package_discovery.py` — add your
class beside `LearnpackV1Discovery`, and one entry to the tuple that builds
`DISCOVERIES_BY_FORMAT` at the bottom of the file. Implement
`FormatPackageDiscoveryPort`: given a `PackageRoot` (an injected "place to fetch files
from" — filesystem or HTTP, you don't care which), read your format's manifests and
return a `DiscoveredPackage`: external id, title, the artifact list, and the content hash
(use the module's `_content_hash` helper — the hash scheme is a compatibility contract).

Rules that are easy to miss:

- Discovery is **hard-failing** by design (ADR-0027): if a manifest is missing or lies,
  raise `PackageDiscoveryError` — a mis-discovered package would *be* the evaluand,
  wrong. The one allowed soft spot is the commission artifact (LearnpackV1's carrier is
  its syllabus), whose absence is a recorded state.
- Discovery is the **sole writer of the artifact `kind` vocabulary** for your format.
  Your extraction adapter (step 3) will read exactly these kinds.
- Never mint a `consumable_url` yourself: ask the root (`root.consumable_url`). A
  filesystem root never declares one (ADR-0028 — serving bytes is transport, not
  deployment).
- The `title` is **persisted** and becomes the name every screen calls the course by
  (ADR-0059), so it must be the package's own words about itself — never composed out of the
  external id, the folder or the slug. `None` is a legitimate answer for a format that
  declares no name, and it costs nothing but a fallback in the console.

**You can stop here and ship.** After this step: the format appears in
`GET /admin/contents/formats` and in the admin form's selector; `register-package --format
<name>` works; a registered course shows its name in `/admin/contents`; re-imports dedupe by content hash; the brief registers absent; profiles are
simply not built yet. In your `FormatCase`, `expected_capabilities=None` says exactly this —
the extraction tests skip instead of failing.

To try it against a real course you need a generator to declare, which step 6 only registers
later. Declare `--generator unknown` instead: the state is a legitimate declaration and it is
repairable — `attribute-generator` links the course once the lineage exists, exactly once
(ADR-0024).

## Step 3 — Extraction adapter (required for any evaluation)

Directory: `backend/app/modules/content_profiling/infrastructure/adapters/` — one module per
format, plus one entry in `ADAPTERS_BY_FORMAT` (`adapters/__init__.py`). Implement
`ExtractionAdapterPort`: read the registered artifacts and produce the entries of the
`ContentProfile`. Declare:

- `PACKAGE_FORMAT` — the same string as step 0. The two modules deliberately do not share
  the constant (module isolation); the contract kit checks they agree.
- `ADAPTER_VERSION` — the identity of *how you read*. Any change in the mapping is a new
  version, and each version needs its own acceptance (step 6).
- `CAPABILITIES` — which `DataRequirement` ids you can supply, chosen from the ids the
  instrument mints (`seed/instruments/`). Do **not** invent data your format does
  not declare: an unmet requirement correctly derives `not_applicable`, and
  matching/readiness surface it. Every value you produce must satisfy the requirement's
  declared `value_domain` (ADR-0020) — the profile aggregate verifies this when built.
- Extraction is deterministic and fails whole (`ExtractionError` → a `failed` profile),
  never half-profiles.

## Step 4 — Brief intake (only if your format carries the commission)

File: `backend/app/modules/evaluand_registry/infrastructure/brief_intake.py`. If your packages
embed the instruction they were generated from (LearnpackV1:
`.learn/initialSyllabus.json`), implement `FormatBriefIntakePort` and register it in
`BRIEF_INTAKES_BY_FORMAT`: `locate()` finds the artifact, `derive()` turns its bytes into
a `DerivedBrief`. Intake is best-effort and non-blocking (ADR-0022): any miss logs and
registers the brief absent — a valid state, not an error. If your format carries nothing,
skip this step entirely; skipping is correct.

A commission is written by a person, so **what carries it is structured and what it says is
not**: both formats wrap free prose (LearnpackV1 in a syllabus field, LearnpackV2 in a
`{"content": …}` envelope). Parse the carrier, then leave the instruction alone — reading
fields out of the prose would substitute your reading for the creator's words. If the
carrier is ever plain text with no envelope at all, `derive()` has to say for itself what
"not a commission" looks like, because there is no parse step to fail it; the kit probes
that case.

Hash the **instruction**, not the payload: a brief's identity is what was asked, so the
same request re-wrapped must not mint a second one.

## Step 5 — Make the contract kit green

Add your `FormatCase` to `backend/tests/format_cases.py` (fixture path + expectations, written as
literals — importing them from your adapter would make the assertions tautological). Run
`uv run pytest tests/test_format_contract.py`. The failing tests are your remaining to-do
list; when they are green, the code side is done. Behavior beyond the contract — your
format's equivalent of LearnpackV1's activity counting — gets its own test file, plus
calibration pins if any criterion depends on empirical thresholds
(`MEASUREMENT.md`).

## Step 6 — The recorded human acts (no code)

These are deliberate human decisions (ADR-0012, ADR-0019, ADR-0031). Take each one; do not
script it away. Once taken, record the outcome in `seed/workbench.yaml` so a rebuilt
local database gets there without asking again — `seed-workbench` replays the acts a manifest
names, and only in local mode (ADR-0045). Replaying a decision is not making one.

1. **Register the generator lineage and version** (once per generator — see
   [Registering courses](../backend/README.md#registering-courses)). The spelling of the name is permanent;
   the version's changelog is write-once.
2. **Accept the extraction** (per adapter version): `accept-extraction --package-format
   <name> --email <admin>`. This is what arms auto-profiling on registration; until then
   profiling stays manual.
3. **Bind the instrument to the format**: add a `bindings` entry with your
   `package_format` (see `seed/instruments/learnpack-course-qa-v1.yaml`). A
   published version is immutable, so this means a new instrument version
   (`bump-instrument` → edit → `import-instrument` → `publish-instrument`). Then check
   `GET /admin/instruments/{instrument_version_id}/matching?package_format=<name>` for the demand your
   format cannot meet — those criteria derive `not_applicable`, which is honest, not
   broken.
4. **Ratify the assessor for the new instrument version** (ADR-0019, command — or the
   `/admin/assessors` button — under
   [Instruments and assessors](../backend/README.md#instruments-and-assessors)).
   Criteria the assessor cannot execute derive `not_assessed` — the visible backlog, not
   a failure.

## Step 7 — Verify end to end

`register-package` → auto-profile (or `profile-content`) → `evaluate --dry-run` while the
instrument is a draft → `declare-study` (name it, and choose its instrument, judge, briefs
and **generator scope** then or later with `update-study` — the scope is
`--all-generator-versions` or one `--generator-version-id` per version the round measures,
and `open-study` refuses a study that never said which, ADR-0044) → `open-study` (**this is
what pins the triple**)
→ `evaluate-study` (the whole dataset in one run) → `show-preview` (what signing off would
write, readable before the irreversible act) → `sign-off-study` →
`show-report` / `show-fitness`.

## What you never touch

Domain and application layers of any module · the ports · the events · the assessors'
logic · the frontend (the form reads formats from the API) · migrations. If a step seems
to require touching one of these, stop: either the step is wrong or it needs an ADR
first.

**What you may well touch:** `backend/app/cli.py`. It is the composition root, and the local intake
path in it has been written against one format at a time before. A helper that names a
specific format's file is a bug the next format uncovers, not a rule you have to work
around — fix it there.

## Where to look next

- [Authoring an instrument](RUNBOOK-authoring-an-instrument.md) — deciding what to ask of
  what you can now read.
- [Measuring what a generator produced](RUNBOOK-measuring.md) — the loop your format
  eventually feeds.
- `../backend/README.md` — setup, the commands around these, and the code's shape.
- `GLOSSARY.md` — what package format, artifact, profile and data requirement mean here.
