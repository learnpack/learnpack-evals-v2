> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — plan for slice 1, already implemented. The current design
> is the series `09`–`13`; the current code plan is in `docs/design/13-code-qa.md`. **Do not use
> this doc as a source for new code nor as a reference for the current state of development.**

# 08 — Code (MVP implementation plan)

> Step 8 of the DDD Starter Modelling Process. **Frozen snapshot**: this is the plan as it was
> written before implementing, not a living backlog. Where the development stands today →
> `../../STATUS.md`. Current rules → `../ARCHITECTURE.md` and the READMEs of `backend/` and
> `frontend/`.
> Scope: human slice of the MVP. Confirmed stack: **Next.js/Tailwind/shadcn on Netlify ·
> FastAPI on Render Starter · Postgres/pgvector on Neon · Clerk (invite-only) as identity**.
> Hard rules: `../ARCHITECTURE.md`. Names: `../GLOSSARY.md`. This plan does **not** close doors to the
> target model (automatic sources, calibration = `[future]`).

## Guiding principle for this plan
The MVP is a **thin slice**: implement only the human backbone (phases 1→4 → golden),
respecting the module boundaries and the Dependency Rule, **without** extra ceremony. Each
subdomain = a Python module; each module = domain / application / infrastructure.

---

## 1. Repo layout (monorepo)

```
/ (repo root)
  CLAUDE.md
  docs/…                      # this design (source of truth)
  backend/                    # FastAPI → deploy to Render (root = /backend)
    app/…                     # see §2
    alembic/                  # migrations
    tests/
    pyproject.toml
    Dockerfile
  frontend/                   # Next.js → deploy to Netlify (root = /frontend)
    src/app/…                 # see §6
    package.json
```

## 2. Hexagonal backend (per module, Dependency Rule)

```
backend/app/
  main.py                     # assembles FastAPI, DI wiring, registers routers (frameworks layer)
  config.py                   # settings from env
  platform/                   # frameworks & drivers
    db.py                     # SQLAlchemy engine/session (Neon)
    events.py                 # in-process dispatcher + outbox (see §4)
    clerk.py                  # Clerk client/JWKS
    security.py               # dependency get_current_assessor / require_admin
  shared/                     # minimal shared kernel
    domain/                   # base DomainEvent, ids, common value objects
    application/              # EventPublisherPort, UnitOfWorkPort
  modules/
    identity/                 # Clerk adapter behind IdentityPort; Assessor resolution
      domain/ application/ infrastructure/
    content_registry/
      domain/                 # EducationalContent, ContentMetadata(open), MetadataEntry, events
      application/            # RegisterContent, UpdateContentMetadata; ports (repo, publisher)
      infrastructure/         # SQLAlchemy repo, LearnPack ACL, FastAPI router
    rubric_authoring/
      domain/ application/ infrastructure/   # seed loader for rubric-v1.json; getRubric query
    evaluation/
      domain/                 # Evaluation (root), EvaluationResult, CriterionScore, invariants
      application/            # SubmitEvaluation; ports
      infrastructure/         # repo, router
    orchestration/
      domain/                 # EvaluationCampaign, Assignment (lifecycle), completion policy
      application/            # OpenCampaign, AssignContent, Cancel/Reassign, on_evaluation_submitted
      infrastructure/         # repos, router
    golden_dataset/
      domain/ application/ infrastructure/   # coverage rule → GoldenReferenceEstablished
    reporting/
      application/            # aggregation.py PURE (mean, dispersion, collapse) — no I/O
      infrastructure/         # composition via public.py of other modules + reports + router
```

Rule: `domain` with no framework imports; `application` defines the ports (Protocols); the
adapters (repos, routers, Clerk, ACL) live in `infrastructure`; `platform` + `main.py` are the
outer layer that injects everything. **No module imports another's internal domain** — they talk
via events (§4) and read-only queries (DTOs).

## 3. Postgres schema (Neon) — sketch per aggregate

```sql
-- identity
assessors(id uuid pk, clerk_user_id text unique, email text, display_name text,
          role text check (role in ('admin','evaluator')), expertise text, created_at timestamptz)

-- content_registry — each row is a concrete VERSION (contentId = version);
-- logical content = (generating_system, external_id). See ADR-0005.
contents(id uuid pk, generating_system text, external_id text, version text not null default '1',
         consumable_url text, metadata jsonb not null default '{}', created_at timestamptz,
         unique(generating_system, external_id, version))
metadata_schemas(generating_system text pk, spec jsonb)   -- seed 'LearnpackV1' (keys+types)

-- rubric_authoring (seed from docs/seed/rubric-v1.json)
rubric_versions(id text pk, rubric_id text, version text, name text, status text,
                scope text, scale_min int, scale_max int, published_at timestamptz,
                unique(rubric_id, version))
criteria(rubric_version_id text references rubric_versions(id), criterion_id text, ord int,
         dimension text, prompt text, guidance text, anchor_low text, anchor_high text,
         qualities jsonb, grounded_in jsonb, eligible_sources jsonb,
         primary key (rubric_version_id, criterion_id))
pedagogical_frameworks(id text pk, citation text)         -- seed

-- orchestration
campaigns(id uuid pk, rubric_version_id text references rubric_versions(id),
          required_evaluations_per_content int, metadata_view jsonb,
          golden_coverage_threshold numeric not null default 1.0,
          status text check (status in ('draft','open','closed')), created_at timestamptz)
campaign_contents(campaign_id uuid, content_id uuid, primary key(campaign_id, content_id))
assignments(id uuid pk, campaign_id uuid, content_id uuid, assessor_id uuid,
            status text check (status in ('assigned','opened','submitted','cancelled')),
            created_at timestamptz, updated_at timestamptz)
-- uniqueness of the active assignment:
create unique index on assignments(campaign_id, content_id, assessor_id)
  where status <> 'cancelled';

-- evaluation
evaluations(id uuid pk, assessor_id uuid, content_id uuid, rubric_version_id text,
            attempt int not null default 1, occurred_at timestamptz, submitted_at timestamptz)
-- Identity = own id. NO uniqueness by (assessor, content, rubricVersion): REPETITIONS of the
-- same assessor on the same (content, rubric) are allowed — e.g. LLMJudge N times for
-- dispersion — and different content versions (content_id is version-specific). CAMPAIGN-
-- AGNOSTIC (no campaign_id): the link to the campaign is the assignment; completion is counted
-- by assignments with status='submitted' (§5). Human anti-duplication lives in the assignment
-- (re-submit on one already 'submitted' → 409). See ADR-0005.
criterion_scores(evaluation_id uuid references evaluations(id), criterion_id text,
                 score int check (score between 1 and 5), comment text,
                 primary key(evaluation_id, criterion_id))

-- completion (emitted by orchestration; alternatively a view)
content_evaluation_completions(campaign_id uuid, content_id uuid, rubric_version_id text,
                               completed_at timestamptz,
                               primary key(campaign_id, content_id))

-- golden_dataset (thin in MVP)
golden_references(campaign_id uuid, rubric_version_id text, coverage numeric,
                  established_at timestamptz, primary key(campaign_id, rubric_version_id))

-- events (append-only, events-first / outbox) — see §4
events(id bigserial pk, occurred_at timestamptz default now(), event_type text,
       aggregate_type text, aggregate_id text, payload jsonb, dispatched_at timestamptz)
```

Implementation notes (concrete decisions):
- `contents.metadata` is open JSONB (ADR-0001), validated in-app against `metadata_schemas`.
  **Seed spec `LearnpackV1`:** `learningObjectives: string_list (required)` ·
  `targetAudience: string (required)` · `prerequisites: string_list (optional)`. No lessonPlan.
  **Validate-on-write / trust-on-read:** validation against the schema runs only on *write*;
  on read it rehydrates without revalidating (a future schema change does not break already-saved reads).
- **Convention for `rubric_versions.id`:** `{rubricId}-{version}` (e.g. `learnpack-pedagogical-v1`),
  deterministic and immutable → idempotent seed.
- **FKs:** intra-module → always. Cross-module (e.g. `evaluations.assessor_id→assessors`,
  `assignments.content_id→contents`, `campaigns.rubric_version_id→rubric_versions`) → declared in
  the MVP (single DB, integrity), but the column references the *id (Published Language)* of the
  owning module; the code **does no cross-module JOINs** (reads via query port). If a module gets
  extracted to its own DB, that FK becomes an app-level check.
- **CHECKs** on all state/role fields: `assessors.role`, `rubric_versions.status`,
  `campaigns.status`, `assignments.status`.
- pgvector is not used in the human MVP, but the extension is already on Neon for the `[future]`.
- **Synchronous SQLAlchemy sessions** in the MVP (not async): simpler, and the workload does not need
  async concurrency; the outbox is atomic either way (async would not break it, but sync is preferable
  here). Revisable if concurrency grows.

## 4. Events-first on Postgres (ADR-0003)

- Each use case, within **one transaction**: writes the aggregate(s) **and** does an `INSERT`
  into `events` (outbox pattern). Atomic commit → "publishing an event = inserting a row".
- After the commit, an **in-process dispatcher** delivers the event to the subscribed policies
  (synchronous in MVP). If a policy fails, it can be reprocessed from `events` (idempotency by
  `event_type + aggregate_id`).
- `[future]` evolution: replace the dispatcher with a real bus / integration-events relay
  (e.g. `QualityJudgmentPublished` → API to LearnPack) without touching the module contracts.

## 5. Mapping command → event → table(s) → policy

| Command (module) | Event | Writes | Policy it triggers |
|---|---|---|---|
| RegisterContent (content_registry) | `ContentRegistered` | contents | — |
| UpdateContentMetadata | `ContentMetadataUpdated` | contents.metadata | — |
| (seed) PublishRubric (rubric_authoring) | `RubricPublished` | rubric_versions, criteria | — |
| OpenCampaign (orchestration) | `CampaignOpened` | campaigns, campaign_contents | — |
| AssignContent | `AssignmentCreated` | assignments | — |
| OpenAssignment | `AssignmentOpened` | assignments.status | — |
| CancelAssignment / Reassign | `AssignmentCancelled` (+ new `AssignmentCreated`) | assignments | — |
| SubmitEvaluation (evaluation) | `EvaluationSubmitted` | evaluations, criterion_scores | (orch) sets `status='submitted'` on ALL open assignments of `(assessor, content)` with `campaign.rubric_version == rubricVersion`; for each affected campaign, if `COUNT(assignments submitted for (campaign, content)) ≥ required` → `ContentEvaluationCompleted` |
| — (orchestration policy) | `ContentEvaluationCompleted` | content_evaluation_completions | (golden) recomputes coverage → if `≥ campaign.golden_coverage_threshold` (default 1.0) → `GoldenReferenceEstablished` |
| — (golden policy) | `GoldenReferenceEstablished` | golden_references | — |

Reporting (MVP) **reads on-demand via the query ports** (public.py) of the owning modules and
**aggregates in Python** (mean + inter-rater), with no event-fed projections nor cross-module JOINs
(ADR-0006). Event-fed CQRS projections = `[future]`.

## 6. Identity with Clerk (ADR-0004)

- **Front (Next on Netlify):** `@clerk/nextjs` — `<ClerkProvider>`, `clerkMiddleware`, `<SignIn/>`
  / `<UserButton/>`. Access **by invitation only** (a feature of Clerk's free tier). A JWT template
  in Clerk so the token carries the necessary claims.
- **Back (FastAPI on Render):** dependency `get_current_assessor` that validates the `Bearer` JWT
  against **Clerk's JWKS** (issuer + exp + signature), extracts `sub`, *upserts* the `assessor`
  (first login) and returns it. `require_admin` checks `role='admin'`.
- **Cross-origin (Netlify ↔ Render):** the token travels in `Authorization: Bearer` (no cross-site
  cookie); the front obtains it with `getToken()` and attaches it to each `fetch`. FastAPI CORS
  middleware: allow the Netlify origin + `Authorization` header.
- It is an **adapter behind the IdentityPort**: the domain only sees `assessorId`. Changing provider
  does not touch the domain.

## 7. API (FastAPI) and pages (Next)

**Evaluator**
- `GET /me/assignments` → pending items of the current assessor (status assigned/opened).
- `GET /assignments/{id}` → metadata (filtered by `metadata_view`) + `RubricSnapshot v1` +
  `consumable_url`.
- `POST /assignments/{id}/open` → `AssignmentOpened` (optional).
- `POST /evaluations` (endpoint in `evaluation`) → `SubmitEvaluation`
  `{assignmentId, scores:[{criterionId, score, comment?}]}`. Reads the assignment via the **query port
  of orchestration** (sync) to get content+rubricVersion. Validates exact coverage of the 5
  criteria and score ∈ [1,5]. If the `Assignment` is already `submitted` → **409** (fast-fail;
  real anti-duplication = assignment transition via policy, ADR-0005). The assignment is marked
  `submitted` by the orchestration policy on hearing `EvaluationSubmitted` (no cross-command).

Pages: `/sign-in` (Clerk) · `/evaluations` (pending list) · `/evaluations/[assignmentId]`
(3-step flow: **1** view metadata → **2** consume content (iframe if the site allows it,
otherwise a link in a new tab) → **3** form of 5 criteria, mandatory score 1–5 + optional
comment, with hints for 1 and 5).

**Admin** (`require_admin`)
- `POST /admin/contents`, `PATCH /admin/contents/{id}/metadata`
- **Content loading = manual, one course at a time** (`POST /admin/contents` + metadata form in the
  admin UI, block 5). There is no LearnPack export → the **ACL `acl_learnpack.py` stays as a
  documented and tested seam (not connected)**. Bulk import CLI = optional `[future]` when a
  canonical JSON exists (`import-content --file <canonical.json>`, no ACL).
- `POST /admin/campaigns` (creates directly in `open`, non-empty `contentSet`; `Draft` not exposed —
  decision C), `POST /admin/campaigns/{id}/assignments`,
  `POST /admin/assignments/{id}/cancel`
- Evaluator invitations: via Clerk (dashboard or Management API).
- `GET /admin/progress` → who evaluated what / pending items per evaluator and per course.
- `GET /admin/reports/scores` → scores per course (individual and average), average per evaluator,
  global, and inter-rater. (Reporting **composes via query ports + aggregates in Python**, no
  cross-module SQL views — ADR-0006. `evaluation.public` exposes a scores query.)

## 8. Content iframe — risk to verify
Many sites block the iframe with `X-Frame-Options`/`CSP frame-ancestors`. **Verify
`https://<curso>.learn-pack.com/` at the start**; if it blocks → fallback "open in new tab".
It is not domain: it lives in the UI.

> Outcome (outside the snapshot): the embed works with LearnPack and the fallback stays the same,
> because the blocking depends on each course's site. See `../../frontend/README.md` and
> `../../STATUS.md`.

## 9. Seed and migrations
- Alembic for the schema.
- Seed script: `docs/seed/rubric-v1.json` → `rubric_versions` + `criteria` +
  `pedagogical_frameworks`; `metadata_schemas` with `LearnpackV1`.
- Rubric v1 is seeded as `status='published'`, locked (no authoring UI).

## 10. Deploy (env per service)
- **Netlify (frontend):** `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
  `NEXT_PUBLIC_API_URL` (Render URL). Base dir `/frontend`.
- **Render Starter (backend):** `DATABASE_URL` (Neon), `CLERK_ISSUER`/`CLERK_JWKS_URL`,
  `CLERK_SECRET_KEY`, `ALLOWED_ORIGINS` (Netlify). Root `/backend`, always on (no cold
  start).
- **Neon:** connection string; pgvector extension enabled (for the `[future]`).

## 11. Testing (minimal focus, not exhaustive)
- Domain: invariants of `Evaluation` (exact coverage, score 1–5; **repetitions are allowed**,
  no uniqueness by assessor/content/rubric) and of the `Assignment` lifecycle (cancel only if not
  submitted; re-submit on `submitted` → 409).
- Completion policy: `COUNT(assignments submitted) ≥ quorum` → `ContentEvaluationCompleted`
  (includes the reassignment case and one evaluation satisfying two campaigns).

## 12. Suggested implementation order
1. Backend scaffolding (platform: db, events, clerk, security) + migrations + seed rubric v1.
2. identity (Clerk) + content_registry (register + metadata).
3. **rubric_authoring (read-only: dtos/queries + repo, no `domain` — see decision A)** +
   evaluation (SubmitEvaluation + invariants; endpoint reads the assignment via the query port of
   orchestration, decision B) + orchestration (campaign/assignments + quorum policy).
4. golden_dataset (coverage) + reporting (read models).
5. frontend: sign-in (Clerk), evaluator's pending items, 3-step flow; **admin: form for manual
   course registration + campaign creation + assignment** (not just read views) — enables the
   demo happy-path (course registration → campaign → evaluate).

> Block 3 decisions: **A** rubric_authoring read-only (rich domain = `[future]` with
> `PublishRubric`). **B** submit lives in `evaluation`, reads the assignment via orchestration's
> query port (sync, allowed); the assignment transition is done by the policy via event
> (no cross-command); 409 = fast-fail. **C** `POST /admin/campaigns` creates directly in `open`
> (non-empty contentSet); `Draft` in the domain but not exposed.

## Related ADRs
`0001` open metadata · `0002` campaigns/assignments/quorum · `0003` Postgres+events ·
`0004` Clerk · `0005` Evaluation identity + content versioning.
