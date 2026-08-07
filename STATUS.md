# STATUS

**The only place in the repo with dated status.** It is **rewritten** whole whenever something
changes; history is not stacked here (that is what git is for). If you find status in any other
document — "already done", "X missing", "N tests green", "verified on such-and-such day" — it is
in the wrong file and belongs here.

_Last updated: 2026-08-07._

## Where we are

**Slice 1 (human MVP): complete and verified locally; the deploy is missing.
Slice 2 (generator QA engine): in implementation by blocks — 6 of 7 done.**

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

### Slice 2 — in implementation by blocks

- **Design:** series `docs/design/09…12` + ADRs 0009–0015 (promoted earlier).
- **Code plan:** **`docs/design/13-code-qa.md`** (promoted) + **ADR-0016** (uniform automated
  assessors). GLOSSARY updated (Source axis `human | automated`;
  `Sufficiency` ex assembly); ARCHITECTURE and CLAUDE.md re-pointed.
- **Decisions taken during implementation:** **ADR-0017** (the declared surface of the
  evaluand is the package — supersedes ADR-0001; realized in block 5), **ADR-0018**
  (declared assessor coverage + `not_assessed` state — refines ADR-0016 §3; block 6
  realizes it), **ADR-0019** (coverage by criteria lineage + ratification per instrument
  version — refines ADR-0016 §3 and ADR-0018; block 6 realizes it) and **ADR-0020**
  (`value_domain` mandatory and verified in `ContentProfile.ok()` — completes ADR-0014;
  realized before block 6, which is its first consumer) and **ADR-0021** (the `fail`
  derived from absence: no quote, with its `derived` origin recorded — refines ADR-0018 §5).
  0018, 0019 and 0021 were **realized in block 6**. GLOSSARY re-updated
  (five states; automated assessor by lineage; `DataRequirement` with its two halves;
  quote demanded only of executed scored).

| Block (`13-code-qa.md` §9) | Status |
|---|---|
| 1. CI (workflow + mypy scoped to new modules) | ✔ |
| 2. Renames + retirement of averages (ADR-0011) | ✔ |
| 3. Evaluand Registry widened | ✔ |
| 4. Evaluation Design (instrument + first real YAML) | ✔ |
| 5. Content Profiling (LearnpackV1 adapter + viewer) | ✔ |
| 6. Automated Evaluation (first assessor) | ✔ |
| 7. Evaluation Studies thin | ✗ |

**Agreed working mode:** branch + PR per block, with branch names and commits that describe
**the change** (feature/fix), never plan stages; Claude commits only inside the working
branches; Marta reviews and merges. Each PR with the full suite green.
(`13-code-qa.md` §8 mentions an old naming scheme — frozen snapshot, not corrected.)

**Experimental-phase convention:** as long as the first published study does not exist,
instrument versions are **disposable** — iterate with cheap versions
(`bump-instrument` → edit → import → publish), deprecate guilt-free, and there is no
compatibility commitment between versions. The full reproducibility commitment starts with the
first published study, which pins its version.

**Pending input from the team:** review and edit the draft of the first instrument
(`docs/seed/instruments/learnpack-course-qa-v1.yaml` — 5 claims / 11 criteria, written as
assistance) and **publish it** when the team makes it its own
(`python -m app.cli publish-instrument --id learnpack-course-qa-v1 --email <admin>`,
`POST /admin/instruments/{id}/publish`, or the **Publish** button in `/admin/instruments`, which
confirms before executing). Until then it stays in `draft` — publication is a
human act (12-define, invariant 5). The minted `data_requirement` ids
(`learning_objectives`, `target_audience`, `prerequisites`, `lesson_inventory`,
`lesson_bodies`, `lesson_activities`) are the contract against which the `LearnpackV1`
adapter v2 declares its capabilities — now with its `value_domain` declared and
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

## Verified

- **Backend suite green: 372 tests** against local Postgres (~13 s). Requires
  `docker compose up -d` in `backend/`; without the DB up, the suite errors, it does not skip.
- **Automated path tested end-to-end** (suite): register → profile → publish a copy
  of the instrument → ratify → evaluate → judgment + findings + events; the frozen package
  `introduction-to-generative-ai` produces the real numbering-drift finding
  (`05`/`06`) via `cr-module-structure-well-formed`.
- **Local mode** (ADR-0008) tested end to end: `seed-demo` idempotent and with `--reset`
  (now it also imports the instrument draft, accepts the `LearnpackV1` extraction and
  profiles the demo courses from their real frozen packages — registered with artifacts,
  so `/admin/profiles` shows the full extraction: inventory, bodies and activities),
  `/me` and `/dev/identities` responding with `X-Dev-User`, and the frontend compiling
  **without any Clerk key**.
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
- **Contract change to keep in mind**: the canonical `import-learnpack` JSON now uses
  `package_format` (formerly `generating_system`); the API renamed `generating_system` →
  `package_format` and `rubric_version_id` → `instrument_version_id`.
- **Rubric v1**: light review (anchors, definitions) pending before the first reference
  campaign (ADR-0015) — outside the first increment of slice 2.
- **Mechanical intake of the `GenerationBrief` from the LearnpackV1 package: pending**
  (small registry PR, before or during block 7 — today all content is left with
  `brief_id = null` and cannot enter paired datasets). Two clarifications agreed
  (2026-08-07): the brief is extracted from the package **at registration, by the
  registry's intake ACL** — never as a profile entry (the brief is the commission's
  identity on the evaluand axis, not pedagogical evidence) — and pairing needs no
  coordination between packages because the **hash identity dedupes**: same effective
  instruction → same hash → same `briefId` across generator versions. LearnpackV2
  (expected soon, with native briefs) arrives through the same intake channel with
  better completeness; the mechanism is built once, with V1's partial brief.
  Design agreed, ADR when
  implementing: the real pipeline has two stages — (user prompt + attached
  material) → syllabus → lessons — and the original prompt **is not persisted**
  (unrecoverable for what was already generated). The brief is registered partial and with its
  completeness declared:
  `brief` = the processed description from `.learn/initialSyllabus.json → courseInfo.description`
  (the operative instruction during lesson generation); `fields` =
  `{origin: ai_derived_syllabus, promptRecorded: false, materialsHash: <hash of
  courseInfo.contentIndex>, materialsSource: ...}` (the material lives in the package, it is
  not duplicated); brief identity/dedup = `hash(description + materialsHash)`. Consequence:
  the A/B pairing holds for "same effective instruction" (lesson stage), not for
  attributing differences to the prompt's wording — `promptRecorded: false` is the datum
  with which studies place that caveat on their own. Note for LearnPack (forward-looking):
  persisting the original prompt in the package (e.g. `courseInfo.originalPrompt`) makes the
  briefs of new content complete. Related: the prompt preprocessor is part of the
  generator's identity — version it in `GeneratorVersion.metadata`.
  (The contamination by hand-typed metadata that motivated part of this discussion was
  resolved by construction: **ADR-0017** removed content metadata from the model — the
  declared surface of the evaluand is the package. The objectives/audience criteria derive
  `not_applicable` in LearnpackV1 until the generator declares those data in the
  package and a new adapter reads them; block 7's matching/readiness will report that
  unmet demand.)
- **Fitness projection for the genetic-algorithm experiment: decided, after block 7.**
  New requirement (2026-08-07): a global numeric value per evaluation — and per
  pedagogical dimension — as the fitness function for evolving the generator. Decision
  taken, **ADR-0022 when implementing**: the fitness is a **read-side projection for
  optimization, never a judgment** — it does not touch ADR-0011 (no aggregate score in
  QA reports; claims/findings remain the product). Computed from `judgment_claims` +
  the qualities → dimension mapping (no schema change); the **formula is versioned and
  pinned** like the instrument (comparability across GA generations). State semantics
  are the anti-gaming core the ADR must fix: `not_assessed` out of the denominator
  (assessor limitation), `no_evidence` and the derived fail penalize (the generator's
  omission — otherwise evolution learns to produce unevaluable content),
  `not_applicable` out. Experiment mapping: individual = `GeneratorVersion` ·
  generation = `Study` (pinned instrument + brief-paired dataset) · fitness =
  projection over the study's judgments — which is why this lands after block 7.
- **Package intake in the registration form: decided, two stages.** Today the UI has no
  reasonable way to load a package's artifacts. Stage 1 (first): **register by link** —
  the form takes the package's base URL (prod) or local folder (dev) and the system
  **discovers the artifacts mechanically** (fetch `learn.json` +
  `.learn/package-manifest.json` → build the locator list, as the adapter/demo already
  do); no storage needed, covers packages LearnPack already serves. Stage 2 (later, own
  ADR): **zip upload + storage** (`PackageStoragePort`, filesystem in dev, S3-compatible
  bucket in prod — a stack decision) for packages not hosted anywhere. Priority rises
  when the GA experiment needs bulk registration.
- **Generator registration is a prerequisite of generator-level analysis.**
  `learnpack-generator 1.0.0` (SemVer; prompt preprocessor not versioned yet — noted in
  its metadata) is registered in the local dev DB; **repeat the act in production
  before registering real content** (there is no command to link a generator to an
  already-registered content: `unknown` is forever, and stays out of generator-level
  accumulation).
- **Outside the first increment** (named in `13-code-qa.md` §9): loop B operational
  (disputes/defects), annotation queues, per-claim validity metrics, `CompareStudies`.

Out of scope by decision, not for lack of time: assessor calibration, CQRS projections,
outgoing integration events and the connected LearnPack ACL — `[future]`, with the slice 2
design preparing the ground.
