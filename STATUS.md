# STATUS

**The only place in the repo with dated status.** It is **rewritten** whole whenever something
changes; history is not stacked here (that is what git is for). If you find status in any other
document — "already done", "X missing", "N tests green", "verified on such-and-such day" — it is
in the wrong file and belongs here.

_Last updated: 2026-08-08._

## Where we are

**Slice 1 (human MVP): complete and verified locally; the deploy is missing.
Slice 2 (generator QA engine): the first increment is code-complete — 7 of 7 blocks,
plus ADR-0024 (generator declaration + late attribution), ADR-0023 (the fitness
projection the genetic-algorithm experiment reads) and ADR-0027 (package intake by
mechanical discovery — in progress, see below) on top of it.**

The repo can be run **without accounts or cloud** (local mode, ADR-0008): see the quickstart in
the root `README.md`.

### Slice 1 — MVP

| Block (`docs/design/08-code.md` §12) | Status |
|---|---|
| 1. Scaffolding + migrations + seed | ✔ |
| 2. identity + content_registry | ✔ |
| 3. rubric_authoring + evaluation + orchestration | ✔ |
| 4. golden_dataset + reporting | ✔ |
| 5. frontend (evaluator + admin console) | ✔ |
| Deploy (§10: Render + Netlify) | ✗ pending |

### Slice 2 — first increment complete

- **Design:** series `docs/design/09…12` + ADRs 0009–0015 (promoted earlier).
- **Code plan:** **`docs/design/13-code-qa.md`** (promoted) + **ADR-0016** (uniform automated
  assessors). GLOSSARY updated (Source axis `human | automated`;
  `Sufficiency` ex assembly); ARCHITECTURE and CLAUDE.md re-pointed.
- **Decisions taken during implementation:** **ADR-0017** (the declared surface of the
  evaluand is the package — supersedes ADR-0001; realized in block 5), **ADR-0018**
  (declared assessor coverage + `not_assessed` state — refines ADR-0016 §3; block 6
  realizes it), **ADR-0019** (coverage by criteria lineage + ratification per instrument
  version — refines ADR-0016 §3 and ADR-0018; block 6 realizes it), **ADR-0020**
  (`value_domain` mandatory and verified in `ContentProfile.ok()` — completes ADR-0014;
  realized before block 6, which is its first consumer), **ADR-0021** (the `fail`
  derived from absence: no quote, with its `derived` origin recorded — refines ADR-0018 §5;
  realized in block 6) and **ADR-0022** (mechanical intake of the `GenerationBrief` at
  content registration, hash identity dedup — **realized in block 7**) and **ADR-0024**
  (the generator link is declared, never defaulted; a discovered one is attributable later,
  once — realized right after block 7), **ADR-0023** (the fitness projection: optimization
  signal per quality, with the denominator that diverges from ADR-0018 §4 — realized after
  block 7), **ADR-0025** (pedagogical frames: the vocabulary is a swappable, disjoint
  namespace — **decided, deliberately not built**) and **ADR-0026** (a claim asserts about
  exactly one quality — realized with ADR-0023, which made the cost visible). GLOSSARY
  reflects
  the five states, the automated assessor by lineage, `DataRequirement` with its two
  halves, the quote demanded only of executed scored, and `unknown` as a declaration.

| Block (`13-code-qa.md` §9) | Status |
|---|---|
| 1. CI (workflow + mypy scoped to new modules) | ✔ |
| 2. Renames + retirement of averages (ADR-0011) | ✔ |
| 3. Evaluand Registry widened | ✔ |
| 4. Evaluation Design (instrument + first real YAML) | ✔ |
| 5. Content Profiling (LearnpackV1 adapter + viewer) | ✔ |
| 6. Automated Evaluation (first assessor) | ✔ |
| 7. Evaluation Studies thin (+ brief intake, ADR-0022) | ✔ |

**After block 7 — the fitness projection (ADR-0023).** A read-side signal for optimization,
never a judgment: `GET /admin/studies/{id}/fitness` and `show-fitness` (CLI) compute, on read,
`pass / (pass + fail + no_evidence)` **per `Quality`**, rolled up to each
`PedagogicalDimension` as the unweighted mean of its **defined** qualities, at three grains —
per content, per generator version (counts pooled across its contents, unknown generators
excluded and named) and per study. `not_assessed` and `not_applicable` stay **outside** the
denominator, which diverges from ADR-0018 §4 on purpose and is stated in the ADR. An empty
denominator answers **`undefined`, never `0`**. Coverage, the formula version and the ratified
assessors travel with every value: dropping `not_assessed` means two assessor sets compute over
different populations, so the GA may only compare within equal coverage. It stays **out of
`study_reports.report`** (ADR-0011 untouched); the console shows it in a separate panel beside
the report, labelled as an optimization signal. Two enabling changes came with it: the
published `InstrumentVersion` now **freezes its `quality → dimension` map**
(`instrument_versions.quality_dimensions`, migration 0013 with backfill) because
`qualities.dimension_id` is global and mutable and would rewrite published studies
retroactively; and `evaluation.public` publishes `get_criterion_outcomes` — the un-aggregated
five states per criterion, which `judgment_claims.evidence_basis` cannot supply (it is counted
per claim, and claims excluded from the denominator have no row at all).

**After block 7 — generator attribution (ADR-0024):** registering a content now **demands a
declaration** — a generator version or an explicit `unknown` — at every entry point (form,
API, canonical bulk import, `register-package`), so the accidental null that
cost a content its place in generator-level accumulation cannot happen silently. And what is
declared unknown is **repairable**: `attribute-generator` (CLI) and
`POST /admin/contents/{id}/generator` record a generator learnt later, **once and one-way**
(`unknown → known`, never `known → other known`), with who and when (migration 0012). A
content attributed after its study opened counts when the report is composed at publish;
reports already published keep their frozen caveat.

**Block 7 delivered:** the `evaluation_studies` module (migration 0011: `studies`,
`study_recipe`, `study_dataset`, `study_reports`) with the lifecycle
declared → prepared → open → published, the report composed on-read at publish (ADR-0006
style; caveats always, never a cross-claim aggregate), the composed queries **matching**
(`GET /admin/instruments/{version}/matching?package_format=…`) and **readiness**
(`GET /admin/studies/{id}/readiness` — gaps per claim plus the ADR-0019 study-level gap
"no ratified assessor"; informs, never blocks), the CLI loop
(`declare-study | pin-study | compose-dataset | open-study | publish-study | show-report`),
and the `/admin/studies` console. The brief intake (ADR-0022) landed in the same PR:
registration derives the brief from `.learn/initialSyllabus.json`, hash identity pairs
registrations automatically, and the intake dispatches through a **per-format adapter
registry** (`BRIEF_INTAKES_BY_FORMAT`, the profiling pattern) — LearnpackV2's native
briefs will be one new entry, no registry or wiring change. `import-learnpack` gained
`--base-dir` (its canonical path also carried a latent ADR-0017 `TypeError`, now fixed:
the canonical JSON takes `artifacts`/`brief_id`/`generator_version_id`/`edit_provenance`,
no `metadata`).

**Agreed working mode:** branch + PR per block, with branch names and commits that describe
**the change** (feature/fix), never plan stages; Claude commits only inside the working
branches; Marta reviews and merges. Each PR with the full suite green.
(`13-code-qa.md` §8 mentions an old naming scheme — frozen snapshot, not corrected.)

**Experimental-phase convention:** as long as the first **real** published study does not
exist, instrument versions are **disposable** — iterate with cheap versions
(`bump-instrument` → edit → import → publish), deprecate guilt-free, and there is no
compatibility commitment between versions. The full reproducibility commitment starts with
the first study the team publishes over real content, which pins its version. (Local demo
studies published while verifying do not count — the local DB is disposable by design.)

**In progress — widening the instrument (3 PRs, this is the first).** The draft now asserts
about **16 of the 21 qualities** (17 claims / 27 criteria) instead of 5, so that the
instrument is ready for the day an LLM-carrying assessor exists. Of the 16 new criteria,
**none is executable by `structural:1`** — they all derive `not_assessed`, which ADR-0023
keeps out of the fitness denominator, so **the fitness does not move because of them yet**.
They are written to document the demand and to make the backlog visible (ADR-0018).
Landed in the first PR: the calibration corpus (5 frozen packages instead of 2), the new
reference doc `docs/MEASUREMENT.md`, and the quality rename
`instruction-authentic-tasks` → `instruction-authentic-problems`.

Landed in the second: the `LearnpackV1` adapter supplies **5 capabilities instead of 3** —
`course_descriptor` (what `learn.json` declares about the course; `difficulty` is the
closest this format has to a declared level, and it stopped being a workbench-only extra)
and `lesson_assessment_items` (the same components `lesson_activities` counts, kept
verbatim instead of tallied; a course with no items reports `absent`, so a claim about
assessment cannot pass on nothing). Exercise-file detection was hardened: nothing keys on
a filename (one course names its exercises `index.html`/`about_me.html`), images and
internal `solution.hide` companions are excluded by what they are, and a lesson artifact is
now recognised **structurally** — it must sit directly under `exercises/<slug>/`, so a
misclassified package asset can no longer invent a lesson named after its directory.
`ADAPTER_VERSION` went back to `"1"`; that `"1"` is not the original one.

Landed in the third: `structural` executes **9 criteria instead of 7** and abstains from
the other 18. `cr-lesson-type-matches-delivery` checks the declared lesson type against the
exercise files actually shipped, **in both directions** — the corpus holds one package that
declares practice and ships none, and another that ships exercises in lessons declared as
reading. `cr-no-lesson-spikes-in-lexical-load` is the first criterion decided by a measure:
`lexical_load` (mean syllables per word over prose), compared against the course's own
median, in `structural/measures.py` — its algorithm is part of the assessor's identity, so
changing it is a new assessor even if no criterion's wording moves.
`backend/tests/test_calibration.py` pins what each of the five packages produces, so the
empirical thresholds cannot drift in silence.

**The immediate effect on the fitness:** `learning-progression` stops being blind. Its
audience quality still has no supply, but `progression-cognitive-demand` is now measured
from the lesson bodies, and one defined quality is enough for a dimension to have a value.
**`objectives-quality` is the only dimension left undefined** among those the instrument
covers (`constructive-alignment` has no claims by design).

`constructive-alignment` is **deliberately left with no claim at all**: it compares declared
objectives against content, and LearnpackV1 declares no learning objectives at course or
lesson level. The dimension answers `undefined`, which is the correct answer rather than a
zero. Same for `objectives-specificity`.

**Pending input from the team:** review and edit the draft of the first instrument
(`docs/seed/instruments/learnpack-course-qa-v1.yaml`, written as
assistance; each claim asserts about exactly one quality, ADR-0026) and **publish it**
when the team makes it its own
(`python -m app.cli publish-instrument --id learnpack-course-qa-v1 --email <admin>`,
`POST /admin/instruments/{id}/publish`, or the **Publish** button in `/admin/instruments`, which
confirms before executing). Until then it stays in `draft` — publication is a
human act (12-define, invariant 5). The minted `data_requirement` ids
(`learning_objectives`, `target_audience`, `prerequisites`, `lesson_inventory`,
`lesson_bodies`, `lesson_activities`) are the contract against which the `LearnpackV1`
adapter v2 declares its capabilities — with its `value_domain` declared and
verified (ADR-0020). (The orphan `practice_exercises` was retired by migration `0008`.)

**Runbook for migration `0008`:** it deletes the `data_requirements` rows without a
`value_domain`, so after `alembic upgrade head` the instrument must be imported again
(`import-instrument`) to re-create the namespace; locally `seed-demo` already does it.
Already-persisted profiles are not re-verified against the value domains (a stored profile
is a past fact): to regenerate them, `seed-demo --reset`.

**Runbook for the renamed quality:** `instruction-authentic-tasks` became
`instruction-authentic-problems` in `docs/seed/pedagogical-reference.yaml`. Two steps, and
any future rename carries the same two.

1. **Run `seed`.** Reference data is **not** touched by `seed-demo --reset`; without this,
   publishing the instrument fails on a quality id that does not exist.
2. **Delete the old row by hand.** Seeding is upsert-by-id and never deletes, so the rename
   leaves the old id behind. Nothing prunes it automatically **on purpose**: a quality can
   be named by a published instrument's frozen `quality → dimension` map, and an automatic
   prune would eat history to tidy a list. Before deleting, check the three things that
   make it safe — no foreign key targets `qualities`, no `instrument_claims.quality_ids`
   names it, and it is absent from every `instrument_versions.quality_dimensions`. On the
   local database all three held and the row is gone; the same check has to be repeated
   wherever else the rename lands.

Rubric v1 keeps the **old wording** in `criteria.qualities` ("Anchoring in authentic
problems or tasks"), and that is correct: it is the frozen human reference (ADR-0015), a
separate artifact that stores display names as free text and references no quality id. The
cost is that the two vocabularies no longer read identically for this one quality —
relevant only to anyone matching them by name.

**Second pending input from the team (block 5):** review the profile samples
(`/admin/profiles` or `app.cli profile-content`) and **accept the extraction** when the team
trusts it (`python -m app.cli accept-extraction --package-format LearnpackV1 --email
<admin>`). Until then, automatic profiling on content registration stays disarmed —
acceptance is a human act (ADR-0012); `seed-demo` auto-accepts it only in local mode.
**Acceptance is per adapter version**, and the version changed with the two new
capabilities, so this act has to be repeated against the current one — an extraction
accepted for the old version says nothing about what the adapter reads now.

**Third pending input from the team (block 6):** once the instrument is published, **ratify it**
for the first automated assessor (`python -m app.cli ratify-assessor --name structural
--version 1 --instrument-version-id learnpack-course-qa-v1 --email <admin>` — ADR-0019; the
initial registration is the first ratification) and evaluate with
`python -m app.cli evaluate --content-id <id> --instrument-version-id <id>`. As long as the
instrument stays in draft, the calibration loop is `evaluate --dry-run` (accepts drafts,
persists nothing). `structural:1` executes 9 criteria and abstains from the other 18
(ADR-0018) — its accumulated `not_assessed` are the visible backlog of the LLM assessor, and
each abstention reason names which capability it needs: the **judgment** itself, or only
**extraction/classification**, after which the pass condition is a count or an order check.
The second kind is the cheaper one to build first.

**Fourth pending input from the team (block 7): publish the first real study.** The loop is
live end to end: register real contents (the brief arrives mechanically when the package
carries `.learn/initialSyllabus.json`), evaluate them, then
`declare-study → pin-study → compose-dataset → open-study → publish-study` (CLI) or the
same acts in `/admin/studies`. Publishing the first real study **ends the
disposable-instrument convention** — the pinned version becomes a reproducibility
commitment. Readiness (`/admin/studies/{id}/readiness`) names the gaps beforehand;
matching reports the ADR-0017 unmet demand (objectives/audience/prerequisites have no
LearnpackV1 supply — those claims accumulate `not_applicable` until the generator declares
the data in the package).

## Verified

- **Backend suite green: 526 tests** against local Postgres (~35 s). Requires
  `docker compose up -d` in `backend/`; without the DB up, the suite errors, it does not skip.
- **The full slice-2 loop tested end-to-end** (suite): register two paired contents (brief
  intake pairs them by hash) → profile → publish an instrument copy → ratify → evaluate →
  declare/pin/compose/open/publish a study → immutable report with the judgment ids
  recorded, the real numbering-drift finding (`05`/`06`) with its quote, generator-level
  distributions with coverage, unknown-generator exclusions, brief completeness and
  abstention causes — and a second publish refused.
- **Attribution proven to be worth something** (suite): a content registered with its
  generator declared unknown is excluded from generator-level accumulation; attributed
  after its study opened, it counts in the report composed at publish and disappears from
  `unknownExclusions`. The one-way rule is tested through the use case and against the
  repository alone (the guard that holds under concurrency).
- **The fitness rules proven on real data** (suite and by hand): over the demo study,
  `objectives-quality` comes back **`undefined`** — LearnpackV1 supplies no objectives, so
  every criterion under it is `not_applicable` and the denominator is 0. A zero there would
  have the GA evolve against a gap in the *package format*, not in the generator.
  It is now the **only** undefined one: `learning-progression` still has no audience supply,
  but `progression-cognitive-demand` is measured from the lesson bodies, and one defined
  quality is enough to give a dimension a value — the point of averaging over *defined*
  qualities rather than scoring the rest zero. `constructive-alignment` does not appear at
  all: the instrument deliberately asserts nothing about it. So **three of the four
  dimensions the instrument covers carry a value**, and the fourth says `undefined` rather
  than being averaged away. `inter-lesson-coherence` is measured from two of its four
  qualities (the numbering-drift `fail` pulling one of them down), and the
  unknown-generator course is counted at study level while excluded from generator level.
- **Manual loop verified in local mode**: `seed-demo --reset` registers the demo courses
  **with intake-derived briefs** (syllabus fixtures in the frozen packages), one linked to
  `learnpack-generator 1.0.0` and one declared unknown → publish + ratify + evaluate both →
  study declared/pinned/composed/opened/published via CLI → `show-report` shows the judgments,
  a populated generator level for the linked course and the other in `unknownExclusions`,
  `promptRecorded: false` per brief, `not_assessed` insufficiencies, the drift finding.
  `attribute-generator` then fills the unknown one and refuses the second attempt.
  `/admin/studies` drives the study acts with a confirm dialog on Publish; `/admin/contents`
  shows brief and generator, and offers the attribution on the unknown cell.
- **Local mode** (ADR-0008) tested end to end: `seed-demo` idempotent and with `--reset`
  (the reset also wipes ratifications, studies and generator versions), `/me` and
  `/dev/identities` responding with `X-Dev-User`, and the frontend compiling **without any
  Clerk key**.
- **Frontend typecheck** clean (`npx tsc --noEmit`).
- **Clerk identity end-to-end**: JWT template with `email`/`name`, invite-only, admin and
  evaluator entering with the correct role. The `backend/README.md` runbook has already been run
  in the development environment.
- **Content iframe** (open risk in `docs/design/08-code.md` §8): tested with a real LearnPack
  `consumable_url`, **it embeds fine**. The "open in a new tab" fallback stays because it
  depends on each course's site.

## Open

- **Deploy**: backend to Render, frontend to Netlify, `ALLOWED_ORIGINS` crossed, and repeat the
  Clerk runbook on the production instance. The DB is already Neon.
- **Contract change to keep in mind**: the canonical `import-learnpack` JSON uses
  `package_format` (formerly `generating_system`) and takes optional `artifacts` /
  `brief_id` / `edit_provenance` (the dead `metadata` key was dropped — ADR-0017);
  `--base-dir` resolves artifact locators locally. Since ADR-0024 **`generator_version_id`
  is required per entry** (null declares unknown). The slice-1 `--acl` path and
  `to_register_command` **retired with ADR-0027** — anyone scripting it must move to
  `register-package`. `POST /admin/contents` likewise requires the key.
- **Rubric v1**: light review (anchors, definitions) pending before the first reference
  campaign (ADR-0015) — outside the first increment of slice 2.
- **The genetic-algorithm experiment itself.** The fitness it reads exists (ADR-0023, above);
  what does not exist is the loop around it — generating a population, registering and
  evaluating it in bulk, and selecting on the signal. Bulk registration — its first
  bottleneck — is now reduced to dropping course folders under `courses/` and running
  `register-package --all` (ADR-0027, below). Also unbuilt on purpose: comparing fitness
  **across** studies, which needs ADR-0023 §7's equal-coverage rule enforced rather than
  merely published (`CompareStudies`).
- **Pedagogical frames: decided, not built (ADR-0025).** The pedagogical vocabulary becomes an
  explicit entity — a frame owning its dimensions and qualities, declared by each
  `InstrumentVersion` and validated against at publish — and **frames are disjoint namespaces**
  (a quality belongs to one frame; two frames declare similar qualities twice). It is not a
  port: the content axis translates something foreign, the vocabulary only needs scoping. The
  mechanism is built **when a second pedagogical approach actually exists**; until then the
  current 5 dimensions / 21 qualities are the implicit first frame and nothing changes. What
  keeps the door open meanwhile is the `quality → dimension` map frozen in the instrument at
  publish (ADR-0023's need, ADR-0025 clause 4). Cost accepted: no comparability across frames at
  any grain, and ADR-0015 reference data bought per frame.

- **Package intake (ADR-0027): stage 1 complete — CLI/local and form.** Registration by
  discovery is live everywhere: `PackageDiscoveryPort` + the per-format discovery ACL read
  `learn.json` + `.learn/config.json` + `.learn/package-manifest.json`, mint the artifact
  list (the discovery ACL is the **sole writer** of the `kind` vocabulary) and hash the
  fetched bytes into `contents.content_hash` (migration 0014) — re-importing an unchanged
  package is a reported no-op, changed content under the same declared version is refused.
  Local courses live in the gitignored `courses/<name>@<version>/` tree, served by a
  dev-only static mount at `/packages`; `register-package --source <url|dir>` registers
  one, `register-package --all` the whole tree; the seeder registers the demo courses
  through the same path. The API side:
  `POST /admin/contents/register-by-source` (http(s) sources; 201 created / 200 unchanged /
  409 content-changed) and `GET /admin/contents/formats`; the admin form registers by
  package URL + generator + provenance — the hand-typed artifact rows are gone, and the
  frontend no longer hardcodes `LearnpackV1`. Stage 2 stays deferred (own ADR): **zip
  upload + storage** (`PackageStoragePort`, filesystem in dev, S3-compatible bucket in
  prod) for packages not hosted anywhere.
- **Generator registration is a prerequisite of generator-level analysis.**
  `learnpack-generator 1.0.0` (SemVer; prompt preprocessor not versioned yet — noted in
  its metadata) is registered in the local dev DB and by `seed-demo`; **repeat the act in
  production before registering real content**, so the declaration ADR-0024 now demands can
  name a real generator instead of falling back to `unknown`.
- **Brief completeness (ADR-0022 consequence):** intake-derived briefs carry
  `promptRecorded: false` — pairing holds for "same effective instruction", not for
  attributing differences to prompt wording. Forward ask to LearnPack: persist the
  original prompt in the package (e.g. `courseInfo.originalPrompt`); the intake will pick
  it up through the same channel. The prompt preprocessor is part of the generator's
  identity — version it in `GeneratorVersion.metadata`.
- **Outside the first increment** (named in `13-code-qa.md` §9): loop B operational
  (disputes/defects), annotation queues, per-claim validity metrics, `CompareStudies`.

Out of scope by decision, not for lack of time: assessor calibration, CQRS projections,
outgoing integration events and the connected LearnPack ACL — `[future]`, with the slice 2
design preparing the ground.
