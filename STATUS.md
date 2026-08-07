# STATUS

**The only place in the repo with dated status.** It is **rewritten** whole whenever something
changes; history is not stacked here (that is what git is for). If you find status in any other
document — "already done", "X missing", "N tests green", "verified on such-and-such day" — it is
in the wrong file and belongs here.

_Last updated: 2026-08-07._

## Where we are

**Slice 1 (human MVP): complete and verified locally; the deploy is missing.
Slice 2 (generator QA engine): the first increment is code-complete — 7 of 7 blocks.**

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
  content registration, hash identity dedup — **realized in block 7**). GLOSSARY reflects
  the five states, the automated assessor by lineage, `DataRequirement` with its two
  halves, and the quote demanded only of executed scored.

| Block (`13-code-qa.md` §9) | Status |
|---|---|
| 1. CI (workflow + mypy scoped to new modules) | ✔ |
| 2. Renames + retirement of averages (ADR-0011) | ✔ |
| 3. Evaluand Registry widened | ✔ |
| 4. Evaluation Design (instrument + first real YAML) | ✔ |
| 5. Content Profiling (LearnpackV1 adapter + viewer) | ✔ |
| 6. Automated Evaluation (first assessor) | ✔ |
| 7. Evaluation Studies thin (+ brief intake, ADR-0022) | ✔ |

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

**Pending input from the team:** review and edit the draft of the first instrument
(`docs/seed/instruments/learnpack-course-qa-v1.yaml` — 5 claims / 11 criteria, written as
assistance) and **publish it** when the team makes it its own
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

**Second pending input from the team (block 5):** review the profile samples
(`/admin/profiles` or `app.cli profile-content`) and **accept the extraction** when the team
trusts it (`python -m app.cli accept-extraction --package-format LearnpackV1 --email
<admin>`). Until then, automatic profiling on content registration stays disarmed —
acceptance is a human act (ADR-0012); `seed-demo` auto-accepts it only in local mode.

**Third pending input from the team (block 6):** once the instrument is published, **ratify it**
for the first automated assessor (`python -m app.cli ratify-assessor --name structural
--version 1 --instrument-version-id learnpack-course-qa-v1 --email <admin>` — ADR-0019; the
initial registration is the first ratification) and evaluate with
`python -m app.cli evaluate --content-id <id> --instrument-version-id <id>`. As long as the
instrument stays in draft, the calibration loop is `evaluate --dry-run` (accepts drafts,
persists nothing). `structural:1` executes 7 criteria and abstains from the 4 judgment ones
(ADR-0018) — its accumulated `not_assessed` are the visible backlog of the LLM assessor.

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

- **Backend suite green: 432 tests** against local Postgres (~15 s). Requires
  `docker compose up -d` in `backend/`; without the DB up, the suite errors, it does not skip.
- **The full slice-2 loop tested end-to-end** (suite): register two paired contents (brief
  intake pairs them by hash) → profile → publish an instrument copy → ratify → evaluate →
  declare/pin/compose/open/publish a study → immutable report with the judgment ids
  recorded, the real numbering-drift finding (`05`/`06`) with its quote, generator-level
  distributions with coverage, unknown-generator exclusions, brief completeness and
  abstention causes — and a second publish refused.
- **Manual loop verified in local mode**: `seed-demo --reset` now registers the demo
  courses **with intake-derived briefs** (syllabus fixtures in the frozen packages) →
  publish + ratify + evaluate both → study declared/pinned/composed/opened/published via
  CLI → `show-report` shows: 2 judgments, empty generator level with both contents in
  `unknownExclusions` (true of the local dataset: demo courses carry no generator
  version), `promptRecorded: false` per brief, `not_assessed` insufficiencies, the drift
  finding. `/admin/studies` drives the same acts with a confirm dialog on Publish.
- **Local mode** (ADR-0008) tested end to end: `seed-demo` idempotent and with `--reset`
  (the reset now also wipes ratifications and studies), `/me` and `/dev/identities`
  responding with `X-Dev-User`, and the frontend compiling **without any Clerk key**.
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
  `package_format` (formerly `generating_system`) and, since block 7, takes optional
  `artifacts` / `brief_id` / `generator_version_id` / `edit_provenance` (the dead
  `metadata` key was dropped — ADR-0017); `--base-dir` resolves artifact locators locally.
- **Rubric v1**: light review (anchors, definitions) pending before the first reference
  campaign (ADR-0015) — outside the first increment of slice 2.
- **Fitness projection for the genetic-algorithm experiment: decided, next.** A global
  numeric value per evaluation — and per pedagogical dimension — as the fitness function
  for evolving the generator. Decision taken, **ADR-0023 when implementing** (0022 was
  taken by the brief intake): the fitness is a **read-side projection for optimization,
  never a judgment** — it does not touch ADR-0011 (no aggregate score in QA reports;
  claims/findings remain the product). Computed from `judgment_claims` + the qualities →
  dimension mapping (no schema change); the **formula is versioned and pinned** like the
  instrument (comparability across GA generations). State semantics are the anti-gaming
  core the ADR must fix: `not_assessed` out of the denominator (assessor limitation),
  `no_evidence` and the derived fail penalize (the generator's omission — otherwise
  evolution learns to produce unevaluable content), `not_applicable` out. Experiment
  mapping: individual = `GeneratorVersion` · generation = `Study` (pinned instrument +
  brief-paired dataset) · fitness = projection over the study's judgments — the studies
  substrate it needs exists as of block 7.
- **Package intake in the registration form: decided, two stages.** Today the UI has no
  reasonable way to load a package's artifacts. Stage 1 (first): **register by link** —
  the form takes the package's base URL (prod) or local folder (dev) and the system
  **discovers the artifacts mechanically** (fetch `learn.json` +
  `.learn/package-manifest.json` → build the locator list, as the adapter/demo already
  do); no storage needed, covers packages LearnPack already serves. Stage 2 (later, own
  ADR): **zip upload + storage** (`PackageStoragePort`, filesystem in dev, S3-compatible
  bucket in prod — a stack decision) for packages not hosted anywhere. Priority rises
  when the GA experiment needs bulk registration.
- **Content registration should require a generator link: decided, ADR when
  implementing.** Today `generator_version_id` defaults silently to null (`unknown`,
  excluded from generator-level accumulation) — an easy accidental loss, and the
  system's purpose is generator QA. The ADR must choose the exact shape (hard-mandatory
  vs. `unknown` as an **explicit act** — a conscious flag, never a silent default; the
  latter matches the house rule that silence is never a declaration) and it supersedes
  the current "unknown allowed" nuance (GLOSSARY, `GeneratorVersion`). Operational
  impact to map: registration form, `import-learnpack` bulk path, `seed-demo` and test
  fixtures. Block 7 makes the cost visible: every unknown content lands in the report's
  `unknownExclusions` caveat and stays out of generator-level accumulation forever.
- **Generator registration is a prerequisite of generator-level analysis.**
  `learnpack-generator 1.0.0` (SemVer; prompt preprocessor not versioned yet — noted in
  its metadata) is registered in the local dev DB; **repeat the act in production
  before registering real content** (there is no command to link a generator to an
  already-registered content: `unknown` is forever, and stays out of generator-level
  accumulation).
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
