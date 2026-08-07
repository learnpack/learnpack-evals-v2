# 13 — Code (slice 2 implementation plan: internal QA)

> **Snapshot of the current design (Aug-2026)** — DDDSMP step 8, second pass: the slice 2
> code plan, analogous to slice 1's `08-code.md`. **Frozen**: it is the plan as it was
> written before implementing, not a living backlog. Where development stands today →
> `../../STATUS.md`. Hard rules → `../ARCHITECTURE.md`. Names → `../GLOSSARY.md`.
> Series: 09 → 13. ADRs: 0009–0016.

## Guiding principle

The first increment of slice 2 is **another thin slice**: the core bit by bit with minimal
supporting (`10-decompose-strategize-qa.md` §implication) — Design with few real claims · **one**
extraction adapter (`LearnpackV1`) · Evaluation minimal automated path · Studies thin. The
**legacy human path (campaigns + Rubric v1 + 1–5) stays intact and functional** at all
times: it is the machinery of the reference panel (ADR-0015). Each block ends with the suite
green.

"thin/no" marks this plan respects (12-define §final):
- Assistance port: **the port only** (`DesignAssistancePort` as a Protocol); no LLM adapters.
- `GeneratorArtifact`: register yes, extract no.
- `StudiesCompared`: no (needs two rounds).
- Per-edit draft events: no (`InstrumentVersionPublished` suffices).

---

## 1. Modules and layout

Existing per-module convention (proven in slice 1): `domain/ · application/ ·
infrastructure/` + `public.py` (the only surface importable by other modules: event constants
+ `<X>Queries` + `get_<x>_queries`). The layer and isolation rules are executable
in `backend/tests/test_architecture.py` — the new modules are covered without changes.

```
backend/app/modules/
  identity/            # stays; extended: automated assessors (kind)              §3.1
  evaluand_registry/   # RENAME of content_registry, widened                      §3.2
  evaluation_design/   # RENAME of rubric_authoring, widened (core, loop B)       §3.3
  content_profiling/   # NEW (supporting, interpretive ACL)                       §3.4
  evaluation/          # stays, reformulated (Pedagogical Evaluation, core)       §3.5
  evaluation_studies/  # NEW (supporting, deliberately thin)                      §3.6
  orchestration/       # stays intact (human path, ADR-0002/0005)
  golden_dataset/      # stays intact
  reporting/           # stays; overall_average/global_average retired            §3.7
```

## 2. Renames (glossary debt) — scope

**Rule:** rename where the old name names a superseded concept; keep where it names the
artifact `Rubric v1`, which **still exists under that name** in the glossary
(reference instrument, ADR-0015 — a different artifact, with a different shape and different rules).

| Rename | Scope |
|---|---|
| `content_registry` → `evaluand_registry` (package) | total |
| `rubric_authoring` → `evaluation_design` (package) | total (only 2 cross imports) |
| `generating_system` → `package_format` | **total**: column in `contents`, PK of `metadata_schemas`, constraint `uq_contents_logical_version`, DTOs, API, frontend |
| `rubric_version_id` → `instrument_version_id` | **columns of shared/consumer tables**: `evaluations`, `campaigns`, `content_evaluation_completions`, `golden_references` (+ event and API payloads). The id of `Rubric v1` IS an instrument version id |
| `rubric_versions` / `criteria` (tables) | **kept**: they specifically store `Rubric v1` (holistic 1–5 + anchors form, which is not migrated) |
| `ContentRegistered` → `ContentVersionRegistered` (event) | rename; `from_payload` accepts old names/keys (replay of historical `events` rows) |
| `RUBRIC_PUBLISHED` | dies (declared, never emitted); superseded by `InstrumentVersionPublished` |

**Structural consequence:** the FKs of those 4 columns toward `rubric_versions` **are
dropped** — the column will contain ids of new instruments OR of `Rubric v1`; referential
validation moves to app level (a pattern already accepted for cross-module references). The
intra-module FKs stay. The existing data in the rubric/evaluation tables is test data and
gets deleted in the migration.

All of this is **migration `0002`** (column/constraint renames) + find/replace in the repos'
`text()` SQL, `cli.py`, DTOs, routers, tests and frontend.

## 3. Postgres schema per aggregate (migrations `0003+`, hand-written DDL)

### 3.1 identity — automated assessors (ADR-0016)

```sql
alter table assessors
  add column kind text not null default 'human' check (kind in ('human','automated')),
  add column source_config jsonb,          -- {name, version, instrumentVersionId, ...}
  alter column clerk_user_id drop not null; -- automated ones have no Clerk
-- upsert by in-code registry: one row per (name, version) of automated assessor (§3.5)
```

The domain already sees only `assessorId`; the provenance chain stays keyed the same for humans
and automated assessors.

### 3.2 evaluand_registry (ex content_registry)

```sql
generator_versions(id uuid pk, name text not null, version text not null, metadata jsonb default '{}',
                   created_at timestamptz, unique(name, version))          -- immutable
generation_briefs(id uuid pk, brief text not null, fields jsonb default '{}',  -- typed fields, demand-driven
                  created_at timestamptz)                                   -- immutable
-- contents is extended:
alter table contents
  add column brief_id uuid references generation_briefs(id),               -- null = absent brief (registered absent)
  add column generator_version_id uuid references generator_versions(id),  -- null = unknown (excluded from accumulation)
  add column edit_provenance text not null default 'unknown'
    check (edit_provenance in ('pure','human_edited','unknown'));
content_package_artifacts(content_id uuid fk, ord int, kind text, locator text, format text,
                          primary key(content_id, ord))                    -- kind OPEN, no enum
generator_artifacts(id uuid pk, generator_version_id uuid fk, kind text, locator text,
                    format text, registered_at timestamptz)                -- register yes, profile no
```

Commands/events: `RegisterGeneratorVersion`→`GeneratorVersionRegistered` ·
`RegisterBrief`→`BriefRegistered` · `RegisterContentVersion` (extends the current
RegisterContent: package + briefId + generatorVersionId + provenance) → `ContentVersionRegistered` ·
`UpdateContentMetadata` (stays) · `RegisterGeneratorArtifact`→`GeneratorArtifactRegistered`.
Public queries: `get_content_package` · `get_available_contents(filters)` ·
`get_generator_version` · `get_brief`.

### 3.3 evaluation_design (ex rubric_authoring)

It keeps the legacy tables and queries (`rubric_versions`, `criteria`, `RubricSnapshot`) for the
human path/reference panel. It adds:

```sql
-- norm-side reference data (seed + rare minting)
pedagogical_dimensions(id text pk, name text)
qualities(id text pk, name text, definition text not null, dimension_id text fk, grounded_in jsonb)
alter table pedagogical_frameworks add column name text, add column scope_note text;  -- stays thin
data_requirements(id text pk, definition text not null, aliases jsonb default '[]',
                  value_domain jsonb, grounded_in jsonb, created_at timestamptz)      -- ADR-0014

-- the Instrument aggregate (root = InstrumentVersion; claims/criteria/bindings as VO rows)
instrument_versions(id text pk,               -- '{instrumentId}-{version}' convention like slice 1
                    instrument_id text, version text, name text, purpose text not null,
                    status text check (status in ('draft','published','deprecated')),
                    published_at timestamptz, published_by uuid,
                    revision_author uuid, revision_reason text, assisted_by jsonb,
                    unique(instrument_id, version))
instrument_claims(instrument_version_id text fk, claim_id text, ord int,
                  statement text not null,               -- one sentence
                  quality_ids jsonb not null,            -- ≥1
                  warrants jsonb not null,               -- framework ids, ≥1 if pedagogical
                  alternative_explanations jsonb not null, -- ≥1 specific to the claim
                  sufficiency jsonb not null,            -- §7.1
                  primary key(instrument_version_id, claim_id))
instrument_criteria(instrument_version_id text fk, criterion_id text, ord int,
                    statement text, pass_condition text not null,   -- verifiable, readable
                    failure_modes jsonb not null,                   -- the failure IS the suggestion
                    claim_ids jsonb not null,                       -- which claims it evidences (≥1)
                    required_data jsonb not null,                   -- data_requirement ids
                    on_missing_evidence text not null default 'no_evidence'
                      check (on_missing_evidence in ('no_evidence','fail')),
                    eligible_sources jsonb not null,               -- values: human | automated
                    condition jsonb,                                -- conditional criteria per task variable
                    primary key(instrument_version_id, criterion_id))
instrument_bindings(instrument_version_id text fk, package_format text,
                    task_variables jsonb default '{}',
                    primary key(instrument_version_id, package_format))
```

- **Mutable draft in rows** (update in place); `PublishInstrument` validates invariants 2–4
  of 12-define and flips `status` atomically → `InstrumentVersionPublished` (payload = the
  snapshot, 11-connect). New version = new rows with stable `claimId`/`criterionId` (lineage).
- **The instrument is 100% declarative** (ADR-0016): it references no executors or checks; the
  criterion→execution mapping lives in each automated assessor (§3.5). The normative thresholds
  ("at least 3 objectives…") live in the `pass_condition` (ADR-0010).
- **Authoring: file + CLI/endpoint, no authoring UI.** `import-instrument --file
  <instrument.yaml>` creates/updates the draft; `POST /admin/instruments/{id}/publish` (or CLI) is
  the human act of publication. The first increment's "few real claims" are written in
  that YAML with the team.
- `MintDataRequirement` happens inside the import/edit (search before minting; duplicate
  lint = a test comparing definitions of repeated ids). No event of its own (no
  consumer; it stays in the table).
- `DesignAssistancePort` is defined in `application/ports.py`; no adapter (thin).
- Public queries: `get_instrument(version) → InstrumentSnapshot` (self-contained: claims +
  criteria + sufficiency + bindings) · `get_data_requirements()` · legacy `get_snapshot`
  (Rubric v1).
- First-increment events: **only** `InstrumentVersionPublished` (+
  `InstrumentDeprecated` when needed). `ClaimDefined`/`CriterionDefined`/
  `DataRequirementMinted` = draft events → thin/no. `InstrumentDefectIdentified` → later
  block (§9, "next").

### 3.4 content_profiling (new)

```sql
content_profiles(id uuid pk, content_id uuid fk, package_format text, adapter_version text,
                 status text check (status in ('ok','failed')), error text,
                 profiled_at timestamptz, unique(content_id, adapter_version))  -- root coordinates; immutable
profile_entries(profile_id uuid fk, data_requirement_id text,     -- Conformist: ids from Design's namespace
                value jsonb,
                provenance text not null check (provenance in ('declared_structured','declared_in_content','absent')),
                quote text, locator jsonb,                        -- verbatim quote + location
                primary key(profile_id, data_requirement_id),
                check (provenance = 'absent' or quote is not null))  -- without a quote it is not evidence (ADR-0009)
profile_extras(profile_id uuid fk, name text, value jsonb, quote text, locator jsonb,
               primary key(profile_id, name))                     -- non-canonical, out of contract
extraction_acceptances(package_format text, adapter_version text, accepted_by uuid,
                       accepted_at timestamptz, primary key(package_format, adapter_version))
```

- **The adapter is infrastructure**: `infrastructure/adapters/learnpack_v1.py` with
  `ADAPTER_VERSION`, `capabilities: set[dataRequirementId]` and `extract(package) → entries`.
  It reads the package's artifacts via a `PackageFetcherPort` (locator → bytes) with an HTTP
  impl and a filesystem impl (fixtures/local). **The investment goes to fixtures**: real
  LearnPack packages frozen in `tests/fixtures/learnpack_v1/`.
- Commands: `ProfileContent(contentId)` (manual — works without acceptance: that is how the
  samples to review are produced) · `AcceptExtraction(packageFormat, adapterVersion)` (admin) ·
  `ReprofileBatch(selection)` (explicit act, never a cascade).
- Policy: `ContentVersionRegistered` → automatic profiling **if** there is an accepted adapter
  for the `package_format` → `ContentProfiled` | `ContentProfilingFailed`.
- Invariant 3 of 12-define by construction: declared capability + absent datum → explicit
  `absent` entry; no capability → no entry.
- Public queries: `get_profile(contentId[, adapterVersion]) → ContentProfileSnapshot` ·
  `get_capabilities(packageFormat)`.

### 3.5 evaluation (reformulated)

```sql
alter table evaluations
  -- rubric_version_id → instrument_version_id already renamed in §2
  add column profile_id uuid references content_profiles(id);  -- null on the human/panel path (no profile)
criterion_outcomes(evaluation_id uuid fk, criterion_id text,
                   outcome text not null check (outcome in ('pass','fail','not_applicable','no_evidence')),
                   quote text, locator jsonb, comment text,
                   primary key(evaluation_id, criterion_id),
                   check (outcome not in ('pass','fail') or quote is not null))  -- scored requires a quote
computed_metrics(evaluation_id uuid fk, metric_id text, value jsonb not null,   -- rows, not events (DP19)
                 primary key(evaluation_id, metric_id))
quality_judgments(id uuid pk, content_id uuid, instrument_version_id text,
                  derived_at timestamptz, coverage jsonb not null)   -- append-only; the most recent per
                                                                     -- (content, instrument) is the current one
judgment_claims(judgment_id uuid fk, claim_id text,
                status text check (status in ('supported','refuted','insufficient')),
                evidence_basis jsonb not null,  -- counts {pass, fail, no_evidence, not_applicable}
                primary key(judgment_id, claim_id))
                -- claim with ALL its criteria not_applicable: NO row here (out of the
                -- denominator — ADR-0011 one level up); recorded in the judgment's coverage
findings(id uuid pk, judgment_id uuid fk, claim_id text, criterion_id text,
         quote text, locator jsonb, failure_mode text not null,      -- the failure mode IS the suggestion
         raised_at timestamptz)
```

`criterion_scores` (1–5) stays intact for the human path/reference panel.

- **`EvaluateContent(contentId, instrumentVersion, assessorId)`** — the automated path:
  1. Loads `InstrumentSnapshot` (design's public) and `ContentProfileSnapshot` (profiling's
     public) — profile prerequisite intact (ADR-0015).
  2. **Mechanical derivation** (pure domain, testable): binding does not cover the format or
     excluded conditional → `not_applicable` · `absent` entry → `no_evidence` (or `fail` if
     `on_missing_evidence='fail'`) · the rest → list of "judgeables".
  3. **Modular automated assessors** (ADR-0016): each one is its own package in
     `evaluation/infrastructure/assessors/<name>/` with `NAME`, `VERSION` and an **internal
     criterion_id → executor mapping** (pure code today; with an LLM inside when that
     adapter arrives — the per-criterion mechanism is an internal detail of the assessor, not
     identity). Each executor reads the profile and returns pass/fail + the quote used (+ raw
     `ComputedMetric`s). Each automated assessor **declares its target instrument**
     (`instrument_version_id`): it owes itself to the criteria of one instrument — relation
     instrument 1 → 0..N automated assessors; humans are not tied to any. An in-code
     registry upserts each (name, version) as a row of `assessors` (§3.1; target in
     `source_config`) and **validates at registration** that the mapping covers all the
     target's criteria; `EvaluateContent` requires an assessor whose target is the requested
     instrument. Any change to the assessor ⇒ new version ⇒ different identity. Two independent
     assessors over the same instrument = the dispersion/agreement case that ADR-0005 enables.
     The consistency between `pass_condition` (norm) and executor (realization) is verified by
     the human layer 2, not by a test.
  4. Persists evaluation + outcomes + metrics → `EvaluationCompleted`.
- Policy: `EvaluationCompleted` → **derive judgment**: applies each claim's sufficiency
  (§7.1) over the outcomes → inserts `quality_judgments` + `judgment_claims` (status + evidence
  basis) + `findings` (per criterion in fail: quote + failure_mode) →
  `QualityJudgmentPublished` + `FindingRaised`. Claim with all its criteria `not_applicable`
  → **excluded from `judgment_claims`**, recorded in coverage. Exact tri-state coverage
  guaranteed by construction (one outcome per criterion of the snapshot).
- `DisagreementDetected`: the structure stays (threshold in the sufficiency), but with a single
  automated assessor the flow is inert in the first increment.
  `DisputeFinding`/`FindingDisputed` → later block (§9, "next").
- Public batch queries: `get_judgments(contentIds, instrumentVersion)` · `get_findings(...)`
  · `get_evaluations(...)` (the legacy scores one stays).

### 3.6 evaluation_studies (new, thin)

```sql
studies(id uuid pk, purpose text not null,
        status text check (status in ('declared','prepared','open','published')),
        instrument_version_id text,           -- null in Declared; pinned ONCE (PinInstrument)
        created_at, opened_at, published_at timestamptz, published_by uuid)
study_recipe(study_id uuid fk, brief_id uuid, primary key(study_id, brief_id))     -- the recipe
study_dataset(study_id uuid fk, content_id uuid, primary key(study_id, content_id)) -- materialized on open
study_reports(study_id uuid pk fk, report jsonb not null, published_at timestamptz) -- immutable
```

- Commands: `DeclareStudy(purpose)` · `PinInstrument` (once, before opening) ·
  `ComposeDataset(briefIds → selects contentIds from what is registered)` · `OpenStudy` (fixed
  dataset) · `PublishStudy` (human act). `CompareStudies` = **no** in the first increment.
- **No subscription-based projection**: on publish, the report is **composed** via query ports
  (ADR-0006 style) — judgments/findings from evaluation, brief/task variables from registry — and
  is materialized immutable in `study_reports`, **recording the judgment ids used**.
  Content: per content, claims with status; at generator level, **distribution of status
  per claim across the dataset**; coverage and caveats **always** (insufficient evidence,
  `unknown` exclusions, unaccepted adapters, disagreements). The per-claim evidence basis
  (§3.5) makes it possible to qualify each "insufficient" with its cause and to exclude from
  the denominator the non-applicable claims. Never a cross-claim aggregate. The patterns
  conditioned by task variables are added when the first task variable exists (non-silent
  deferral).
- Events: `StudyDeclared` · `InstrumentPinned` · `StudyOpened` · `StudyPublished`.
- Studies **never commands** Orchestration; the human wiring is done by the actor via UI.

### 3.7 reporting

- **Retire `overall_average`/`global_average`** from `aggregation.py`, from the endpoint
  `/admin/reports/scores`, from the frontend admin view and from their tests (ADR-0011). The
  per-criterion average across assessors + inter-rater dispersion stay (ADR-0006).
- The slice 2 report is served by `evaluation_studies` (§3.6); reporting gains no new pieces
  in the first increment.

## 4. Events-first (no mechanism changes)

ADR-0003's outbox + in-process dispatcher continues as is (`OutboxEventPublisher`,
`EventDispatcher`, `UnitOfWork.commit()` → post-commit dispatch). The new modules copy the
existing policy pattern: translate `payload` via `…Fact.from_payload` (Published Language),
own transaction, idempotency via conditional insertion (repos that return "just
inserted"). Payloads camelCase; the `from_payload` of renamed events accept the
old names/keys (replay of historical `events` rows).

## 5. Command → event → tables → policy mapping (new flow)

| Command (module) | Event | Writes | Policy it triggers |
|---|---|---|---|
| RegisterGeneratorVersion (registry) | `GeneratorVersionRegistered` | generator_versions | — |
| RegisterBrief (registry) | `BriefRegistered` | generation_briefs | — |
| RegisterContentVersion (registry) | `ContentVersionRegistered` | contents, content_package_artifacts | (profiling) if there is an accepted adapter → ProfileContent |
| RegisterGeneratorArtifact (registry) | `GeneratorArtifactRegistered` | generator_artifacts | — |
| ProfileContent (profiling) | `ContentProfiled` \| `ContentProfilingFailed` | content_profiles, profile_entries, profile_extras | — (evaluating is explicit in the first increment) |
| AcceptExtraction (profiling) | `ExtractionAccepted` | extraction_acceptances | — |
| import-instrument + PublishInstrument (design) | `InstrumentVersionPublished` (payload = snapshot) | instrument_versions, instrument_claims, instrument_criteria, instrument_bindings | — |
| EvaluateContent (evaluation) | `EvaluationCompleted` | evaluations, criterion_outcomes, computed_metrics | (evaluation) derive judgment |
| — (evaluation policy) | `QualityJudgmentPublished` + `FindingRaised` | quality_judgments, judgment_claims, findings | — (Studies composes on-read) |
| DeclareStudy / PinInstrument / ComposeDataset / OpenStudy (studies) | `StudyDeclared` / `InstrumentPinned` / `StudyOpened` | studies, study_recipe, study_dataset | — |
| PublishStudy (studies) | `StudyPublished` | study_reports | — |

The legacy human flow (SubmitEvaluation → quorum → golden) stays exactly as is.

## 6. Composed queries (no state owner — ADR-0006 composition)

They live in `evaluation_studies` (the operational consumer), composed via other modules'
`public.py`:

- **Matching:** demand side (`required_data` of an `InstrumentSnapshot`) × supply side
  (`get_capabilities(packageFormat)`) → expected coverage + unmet demand.
  `GET /admin/instruments/{version}/matching?package_format=…`.
- **Readiness:** per study — pending/published instrument × matching × `ExtractionAccepted`
  → gaps **per claim** ("claim without criteria" · "criterion without a datum in this format" ·
  "extraction not accepted"). **It informs, it does not block**. `GET /admin/studies/{id}/readiness`.

## 7. 12-define deferrals — decided by this plan

1. **Sufficiency (ex assembly — the rename belongs to this plan; see GLOSSARY):** `sufficiency`
   jsonb per claim, expressed with the psychometric taxonomy of decision models:
   - `{"rule": "conjunctive"}` — default and the **only one implemented** in the first increment:
     **supported** if all the criteria evidencing the claim are `scored=pass` ·
     **refuted** if ≥1 is `scored=fail` (one quoted counterexample refutes) · **insufficient**
     in any other case. Deliberate error asymmetry: the conjunctive produces false
     "refuted" before false "supported" — the right thing for internal QA (the false refuted
     costs a review with the quote in sight; the false supported hides a defect).
   - `existential` and `m_of_n`: documented vocabulary, **not built** (demand-driven).
   - **Compensatory (weights / averages / point threshold): forbidden** — ADR-0011 one level
     up. Quality Matters-style gates unnecessary: in the conjunctive every criterion is already
     essential.
   - **Design guidance (k12-teacher-skills lesson):** the quantifier belongs to the criterion's
     `pass_condition` ("at least 2 of 3 objectives…"), not to the sufficiency; a
     claim that seems to ask for `m_of_n` is a decomposition smell (is it two claims?). The
     multi-assessor agreement thresholds and `DisagreementDetected` will enter this field when
     they exist.
2. **Per-claim validity metrics (ADR-0015):** out of the first increment. Trigger: first
   reference campaign completed + usable golden. No schema until then.
3. **Annotation queues (layer 2):** out of the first increment. Planned realization:
   reuse orchestration's campaigns/assignments (12-define indicates it); no code
   now.
4. **Structured value domains:** optional `data_requirements.value_domain` jsonb, minimal
   spec `{type: string|string_list|number|enum|levels, values?, citation?}` — only what
   the first claims consume.

## 8. CI and working mode

- `.github/workflows/ci.yml`: backend (ruff check + **strict mypy scoped to the new slice 2
  modules** — the legacy is explicitly excluded; cleaning it up is an optional future
  task — + pytest with Postgres as a service container; the suite **includes**
  `test_architecture.py`, which lints the ARCHITECTURE §3 rule) · frontend (`npm ci` +
  `tsc --noEmit`).
- **No import-linter**: it would be redundant with the executable architecture tests.
- **Branch + PR per block** (`slice2/<nn>-<name>`); each PR is merged with the full suite
  green — the legacy human path is demonstrated intact at every step.

## 9. Implementation order by blocks

1. **CI** (§8) — first, it protects everything else.
2. **Renames + debts** (§2 + §3.7): migration `0002`, packages, API/frontend, retirement of
   averages (ADR-0011), payload aliases. The legacy suite green demonstrates the human
   path intact.
3. **Widened Evaluand Registry** (§3.2): tables + commands + events + admin endpoints +
   minimal admin forms (generator, brief, content with package).
4. **Evaluation Design** (§3.3): reference data (seed of dimensions/qualities/frameworks +
   data_requirements) + Instrument aggregate + import/publish + `InstrumentSnapshot` +
   domain invariants with tests. Here the **first real instrument (few
   claims)** is written with the team.
5. **Content Profiling** (§3.4): aggregate + `LearnpackV1` adapter + fixtures + acceptance +
   profiling policy + **profile viewer** (read-only, with quotes — the designer's
   workbench, ADR-0012). Blocks 4 and 5 are parallelizable after 3.
6. **Automated Evaluation** (§3.5 + §3.1): mechanical derivation + first automated
   assessor + judgment/findings + events.
7. **Evaluation Studies thin** (§3.6 + §6): lifecycle + readiness/matching + publication +
   report + minimal UI (declare/compose/open/publish + report view).

**Next (outside the first increment):** operational loop B (`DisputeFinding`,
`InstrumentDefectIdentified`, diagnosis) · annotation queues · light revision of Rubric v1
+ first reference campaign · per-claim validity metrics · `CompareStudies`.

## 10. Testing (focus per block)

- **Domain (rich in the core):** Instrument publication invariants (complete claims/criteria,
  binding ≥1, post-publish immutability, id lineage) · mechanical derivation of the
  tri-state (case table: capability × entry × on_missing_evidence × conditionals) ·
  conjunctive sufficiency (incl. exclusion of the all-`not_applicable` claim) · Study
  invariants (pin once, fixed dataset, immutable publish).
- **Adapters via fixtures (Profiling's investment):** frozen LearnPack packages → exact
  expected profile, quotes included; case "capability without a datum → explicit absent".
- **Automated assessors:** registration validation (target coverage) + executors with
  per-criterion cases.
- **Policies:** profiling on-register (with/without acceptance) · judgment on-completed
  (idempotency via conditional insertion, existing pattern).
- **E2E API:** the slice's happy path — register generator/brief/content → profile → publish
  instrument → evaluate → open study → publish → report with coverage and caveats.
- **Architecture:** `test_architecture.py` covers the new modules without changes.
- Existing conventions: flat tests in `tests/`, conftest fixtures (`cleanup` is
  extended with the new tables in FK order), no formal factories.

## Decisions recorded while writing this plan

Rename scope (§2, incl. keeping the `Rubric v1` tables) · instrument authoring
via YAML + CLI/endpoint with no UI · modular automated assessors with a target instrument
(**ADR-0016**) · sufficiency with psychometric taxonomy and compensatory forbidden (§7.1) ·
per-claim evidence basis and denominator rule one level up (§3.5) ·
append-only `QualityJudgment` with judgment ids pinned in the report (§3.5–3.6) · CI without
import-linter and strict mypy scoped to new modules (§8).

## Related ADRs

`0003` outbox (continues) · `0005` Evaluation identity (continues) · `0006` composition via query
ports (the pattern for the report and the composed queries) · `0009`–`0015` (the design this plan
realizes) · **`0016` automated assessors** (born with this plan).
