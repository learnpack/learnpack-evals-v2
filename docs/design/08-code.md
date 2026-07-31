# 08 — Code (plan de implementación del MVP)

> Paso 8 del DDD Starter Modelling Process. **Snapshot congelado**: es el plan tal como se
> escribió antes de implementar, no un backlog vivo. En qué punto está el desarrollo hoy →
> `../../STATUS.md`. Reglas vigentes → `../ARCHITECTURE.md` y los READMEs de `backend/` y
> `frontend/`.
> Alcance: slice humano del MVP. Stack confirmado: **Next.js/Tailwind/shadcn en Netlify ·
> FastAPI en Render Starter · Postgres/pgvector en Neon · Clerk (invite-only) como identidad**.
> Reglas duras: `../ARCHITECTURE.md`. Nombres: `../GLOSSARY.md`. Este plan **no** cierra puertas al
> modelo objetivo (fuentes automáticas, calibración = `[futuro]`).

## Principio rector para este plan
El MVP es una **rebanada fina**: implementar solo el backbone humano (fases 1→4 → golden),
respetando los boundaries de módulo y la Dependency Rule, **sin** ceremonia de más. Cada
subdominio = un módulo Python; cada módulo = domain / application / infrastructure.

---

## 1. Layout del repo (monorepo)

```
/ (repo root)
  CLAUDE.md
  docs/…                      # este diseño (fuente de verdad)
  backend/                    # FastAPI → deploy a Render (root = /backend)
    app/…                     # ver §2
    alembic/                  # migraciones
    tests/
    pyproject.toml
    Dockerfile
  frontend/                   # Next.js → deploy a Netlify (root = /frontend)
    src/app/…                 # ver §6
    package.json
```

## 2. Backend hexagonal (por módulo, Dependency Rule)

```
backend/app/
  main.py                     # ensambla FastAPI, DI wiring, registra routers (capa frameworks)
  config.py                   # settings desde env
  platform/                   # frameworks & drivers
    db.py                     # engine/session SQLAlchemy (Neon)
    events.py                 # dispatcher in-process + outbox (ver §4)
    clerk.py                  # cliente/JWKS de Clerk
    security.py               # dependency get_current_assessor / require_admin
  shared/                     # shared kernel mínimo
    domain/                   # base DomainEvent, ids, value objects comunes
    application/              # EventPublisherPort, UnitOfWorkPort
  modules/
    identity/                 # Clerk adapter detrás de IdentityPort; resolución de Assessor
      domain/ application/ infrastructure/
    content_registry/
      domain/                 # EducationalContent, ContentMetadata(open), MetadataEntry, events
      application/            # RegisterContent, UpdateContentMetadata; ports (repo, publisher)
      infrastructure/         # repo SQLAlchemy, ACL LearnPack, router FastAPI
    rubric_authoring/
      domain/ application/ infrastructure/   # seed loader de rubric-v1.json; getRubric query
    evaluation/
      domain/                 # Evaluation (root), EvaluationResult, CriterionScore, invariantes
      application/            # SubmitEvaluation; ports
      infrastructure/         # repo, router
    orchestration/
      domain/                 # EvaluationCampaign, Assignment (lifecycle), completion policy
      application/            # OpenCampaign, AssignContent, Cancel/Reassign, on_evaluation_submitted
      infrastructure/         # repos, router
    golden_dataset/
      domain/ application/ infrastructure/   # coverage rule → GoldenReferenceEstablished
    reporting/
      application/            # aggregation.py PURA (media, dispersión, collapse) — sin I/O
      infrastructure/         # composición vía public.py de otros módulos + reports + router
```

Regla: `domain` sin imports de framework; `application` define los ports (Protocols); los
adapters (repos, routers, Clerk, ACL) viven en `infrastructure`; `platform` + `main.py` son la
capa externa que inyecta todo. **Ningún módulo importa el dominio interno de otro** — se hablan
por eventos (§4) y por queries de solo-lectura (DTOs).

## 3. Esquema Postgres (Neon) — sketch por agregado

```sql
-- identity
assessors(id uuid pk, clerk_user_id text unique, email text, display_name text,
          role text check (role in ('admin','evaluator')), expertise text, created_at timestamptz)

-- content_registry — cada fila es una VERSIÓN concreta (contentId = versión);
-- contenido lógico = (generating_system, external_id). Ver ADR-0005.
contents(id uuid pk, generating_system text, external_id text, version text not null default '1',
         consumable_url text, metadata jsonb not null default '{}', created_at timestamptz,
         unique(generating_system, external_id, version))
metadata_schemas(generating_system text pk, spec jsonb)   -- seed 'LearnpackV1' (keys+tipos)

-- rubric_authoring (seed desde docs/seed/rubric-v1.json)
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
-- unicidad de assignment activa:
create unique index on assignments(campaign_id, content_id, assessor_id)
  where status <> 'cancelled';

-- evaluation
evaluations(id uuid pk, assessor_id uuid, content_id uuid, rubric_version_id text,
            attempt int not null default 1, occurred_at timestamptz, submitted_at timestamptz)
-- Identidad = id propio. SIN unicidad por (assessor, content, rubricVersion): se permiten
-- REPETICIONES del mismo assessor sobre el mismo (content, rubric) — p.ej. LLMJudge N veces para
-- dispersión — y distintas versiones de contenido (content_id es version-specific). CAMPAIGN-
-- AGNOSTIC (sin campaign_id): el nexo con la campaña es el assignment; la completitud se cuenta
-- por assignments con status='submitted' (§5). La anti-duplicación humana vive en el assignment
-- (re-submit sobre uno ya 'submitted' → 409). Ver ADR-0005.
criterion_scores(evaluation_id uuid references evaluations(id), criterion_id text,
                 score int check (score between 1 and 5), comment text,
                 primary key(evaluation_id, criterion_id))

-- completitud (emitido por orchestration; alternativamente una vista)
content_evaluation_completions(campaign_id uuid, content_id uuid, rubric_version_id text,
                               completed_at timestamptz,
                               primary key(campaign_id, content_id))

-- golden_dataset (thin en MVP)
golden_references(campaign_id uuid, rubric_version_id text, coverage numeric,
                  established_at timestamptz, primary key(campaign_id, rubric_version_id))

-- events (append-only, events-first / outbox) — ver §4
events(id bigserial pk, occurred_at timestamptz default now(), event_type text,
       aggregate_type text, aggregate_id text, payload jsonb, dispatched_at timestamptz)
```

Notas de implementación (decisiones concretas):
- `contents.metadata` es JSONB abierto (ADR-0001), validado en app contra `metadata_schemas`.
  **Spec seed `LearnpackV1`:** `learningObjectives: string_list (required)` ·
  `targetAudience: string (required)` · `prerequisites: string_list (optional)`. Sin lessonPlan.
  **Validate-on-write / trust-on-read:** la validación contra el schema corre solo al *escribir*;
  al leer se rehidrata sin revalidar (un cambio futuro de schema no rompe lecturas ya guardadas).
- **Convención de `rubric_versions.id`:** `{rubricId}-{version}` (p.ej. `learnpack-pedagogical-v1`),
  determinístico e inmutable → seed idempotente.
- **FKs:** intra-módulo → siempre. Cross-módulo (p.ej. `evaluations.assessor_id→assessors`,
  `assignments.content_id→contents`, `campaigns.rubric_version_id→rubric_versions`) → declaradas en
  el MVP (una sola DB, integridad), pero la columna referencia el *id (Published Language)* del
  módulo dueño; el código **no hace JOINs cross-módulo** (lecturas por query port). Si un módulo se
  extrae a su DB, esa FK pasa a chequeo a nivel de app.
- **CHECKs** en todos los campos de estado/rol: `assessors.role`, `rubric_versions.status`,
  `campaigns.status`, `assignments.status`.
- pgvector no se usa en el MVP humano, pero la extensión ya está en Neon para el `[futuro]`.
- **Sesiones SQLAlchemy síncronas** en el MVP (no async): más simples, y el workload no necesita
  concurrencia async; el outbox es atómico igual (async no lo rompería, pero sync es preferible
  acá). Revisable si crece la concurrencia.

## 4. Events-first sobre Postgres (ADR-0003)

- Cada use case, dentro de **una transacción**: escribe el/los agregado(s) **y** hace `INSERT`
  en `events` (patrón outbox). Commit atómico → "publicar un evento = insertar fila".
- Tras el commit, un **dispatcher in-process** entrega el evento a las policies suscritas
  (síncrono en MVP). Si una policy falla, se puede reprocesar desde `events` (idempotencia por
  `event_type + aggregate_id`).
- Evolución `[futuro]`: reemplazar el dispatcher por un bus real / relay de integration events
  (p.ej. `QualityJudgmentPublished` → API a LearnPack) sin tocar los contratos de módulo.

## 5. Mapeo comando → evento → tabla(s) → policy

| Comando (módulo) | Evento | Escribe | Policy que dispara |
|---|---|---|---|
| RegisterContent (content_registry) | `ContentRegistered` | contents | — |
| UpdateContentMetadata | `ContentMetadataUpdated` | contents.metadata | — |
| (seed) PublishRubric (rubric_authoring) | `RubricPublished` | rubric_versions, criteria | — |
| OpenCampaign (orchestration) | `CampaignOpened` | campaigns, campaign_contents | — |
| AssignContent | `AssignmentCreated` | assignments | — |
| OpenAssignment | `AssignmentOpened` | assignments.status | — |
| CancelAssignment / Reassign | `AssignmentCancelled` (+ nuevo `AssignmentCreated`) | assignments | — |
| SubmitEvaluation (evaluation) | `EvaluationSubmitted` | evaluations, criterion_scores | (orch) pone `status='submitted'` en TODAS las assignments abiertas de `(assessor, content)` con `campaign.rubric_version == rubricVersion`; para cada campaña afectada, si `COUNT(assignments submitted for (campaign, content)) ≥ required` → `ContentEvaluationCompleted` |
| — (policy orchestration) | `ContentEvaluationCompleted` | content_evaluation_completions | (golden) recalcula coverage → si `≥ campaign.golden_coverage_threshold` (default 1.0) → `GoldenReferenceEstablished` |
| — (policy golden) | `GoldenReferenceEstablished` | golden_references | — |

Reporting (MVP) **lee on-demand por los query ports** (public.py) de los módulos dueños y
**agrega en Python** (media + inter-rater), sin proyecciones por eventos ni JOINs cross-módulo
(ADR-0006). Las proyecciones CQRS alimentadas por eventos = `[futuro]`.

## 6. Identidad con Clerk (ADR-0004)

- **Front (Next en Netlify):** `@clerk/nextjs` — `<ClerkProvider>`, `clerkMiddleware`, `<SignIn/>`
  / `<UserButton/>`. Acceso **solo por invitación** (feature del free de Clerk). Un JWT template
  en Clerk para que el token traiga los claims necesarios.
- **Back (FastAPI en Render):** dependency `get_current_assessor` que valida el `Bearer` JWT
  contra el **JWKS de Clerk** (issuer + exp + firma), extrae `sub`, hace *upsert* del `assessor`
  (primer login) y lo devuelve. `require_admin` chequea `role='admin'`.
- **Cross-origin (Netlify ↔ Render):** el token viaja en `Authorization: Bearer` (no cookie
  cross-site); el front lo obtiene con `getToken()` y lo adjunta a cada `fetch`. Middleware CORS
  de FastAPI: permitir el origin de Netlify + header `Authorization`.
- Es un **adapter detrás del IdentityPort**: el dominio solo ve `assessorId`. Cambiar de proveedor
  no toca el dominio.

## 7. API (FastAPI) y páginas (Next)

**Evaluador**
- `GET /me/assignments` → pendientes del assessor actual (status assigned/opened).
- `GET /assignments/{id}` → metadata (filtrada por `metadata_view`) + `RubricSnapshot v1` +
  `consumable_url`.
- `POST /assignments/{id}/open` → `AssignmentOpened` (opcional).
- `POST /evaluations` (endpoint en `evaluation`) → `SubmitEvaluation`
  `{assignmentId, scores:[{criterionId, score, comment?}]}`. Lee la assignment por el **query port
  de orchestration** (sync) para sacar content+rubricVersion. Valida cobertura exacta de los 5
  criteria y score ∈ [1,5]. Si el `Assignment` ya está `submitted` → **409** (fast-fail;
  anti-duplicación real = transición de la assignment vía policy, ADR-0005). La assignment la marca
  `submitted` la policy de orchestration al oír `EvaluationSubmitted` (sin comando cruzado).

Páginas: `/sign-in` (Clerk) · `/evaluations` (lista de pendientes) · `/evaluations/[assignmentId]`
(flujo 3 pasos: **1** ver metadata → **2** consumir contenido (iframe si el sitio lo permite,
si no link en pestaña nueva) → **3** formulario de 5 criteria, score 1–5 obligatorio + comentario
opcional, con hints de 1 y 5).

**Admin** (`require_admin`)
- `POST /admin/contents`, `PATCH /admin/contents/{id}/metadata`
- **Carga de contenido = manual, de a un curso** (`POST /admin/contents` + form de metadata en la
  admin UI, bloque 5). No hay export de LearnPack → el **ACL `acl_learnpack.py` queda como seam
  documentado y testeado (no conectado)**. Bulk import CLI = `[futuro]` opcional cuando exista un
  JSON canónico (`import-content --file <canonical.json>`, sin ACL).
- `POST /admin/campaigns` (crea directo en `open`, `contentSet` no vacío; `Draft` no expuesto —
  decisión C), `POST /admin/campaigns/{id}/assignments`,
  `POST /admin/assignments/{id}/cancel`
- Invitaciones de evaluadores: vía Clerk (dashboard o Management API).
- `GET /admin/progress` → quién evaluó qué / pendientes por evaluador y por curso.
- `GET /admin/reports/scores` → scores por curso (individual y promedio), promedio por evaluador,
  global, e inter-rater. (Reporting **compone vía query ports + agrega en Python**, no vistas
  SQL cross-módulo — ADR-0006. `evaluation.public` expone una query de scores.)

## 8. iframe del contenido — riesgo a verificar
Muchos sitios bloquean el iframe con `X-Frame-Options`/`CSP frame-ancestors`. **Verificar
`https://<curso>.learn-pack.com/` al empezar**; si bloquea → fallback "abrir en pestaña nueva".
No es dominio: vive en la UI.

> Desenlace (fuera del snapshot): el embed funciona con LearnPack y el fallback se mantiene igual,
> porque el bloqueo depende del sitio de cada curso. Ver `../../frontend/README.md` y
> `../../STATUS.md`.

## 9. Seed y migraciones
- Alembic para el schema.
- Seed script: `docs/seed/rubric-v1.json` → `rubric_versions` + `criteria` +
  `pedagogical_frameworks`; `metadata_schemas` con `LearnpackV1`.
- Rubric v1 se siembra como `status='published'`, locked (sin UI de autoría).

## 10. Deploy (env por servicio)
- **Netlify (frontend):** `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
  `NEXT_PUBLIC_API_URL` (URL de Render). Base dir `/frontend`.
- **Render Starter (backend):** `DATABASE_URL` (Neon), `CLERK_ISSUER`/`CLERK_JWKS_URL`,
  `CLERK_SECRET_KEY`, `ALLOWED_ORIGINS` (Netlify). Root `/backend`, siempre encendido (sin cold
  start).
- **Neon:** connection string; extensión pgvector habilitada (para `[futuro]`).

## 11. Testing (foco mínimo, no exhaustivo)
- Dominio: invariantes de `Evaluation` (cobertura exacta, score 1–5; **se permiten repeticiones**,
  sin unicidad por assessor/content/rubric) y del lifecycle de `Assignment` (cancel solo si no
  submitted; re-submit sobre `submitted` → 409).
- Policy de completitud: `COUNT(assignments submitted) ≥ quorum` → `ContentEvaluationCompleted`
  (incluye caso de reasignación y de una evaluación que satisface dos campañas).

## 12. Orden sugerido de implementación
1. Scaffolding backend (platform: db, events, clerk, security) + migraciones + seed rubric v1.
2. identity (Clerk) + content_registry (register + metadata).
3. **rubric_authoring (read-only: dtos/queries + repo, sin `domain` — ver decisión A)** +
   evaluation (SubmitEvaluation + invariantes; endpoint lee la assignment por el query port de
   orchestration, decisión B) + orchestration (campaign/assignments + policy de quórum).
4. golden_dataset (coverage) + reporting (read models).
5. frontend: sign-in (Clerk), pendientes del evaluador, flujo 3 pasos; **admin: form de alta
   manual de curso + creación de campaña + asignación** (no solo vistas de lectura) — habilita el
   happy-path del demo (alta de cursos → campaña → evaluar).

> Decisiones de bloque 3: **A** rubric_authoring read-only (domain rico = `[futuro]` con
> `PublishRubric`). **B** submit vive en `evaluation`, lee assignment por query port de
> orchestration (sync, permitido); la transición de la assignment la hace la policy vía evento
> (sin comando cruzado); 409 = fast-fail. **C** `POST /admin/campaigns` crea directo en `open`
> (contentSet no vacío); `Draft` en el dominio pero no expuesto.

## ADRs relacionados
`0001` metadata abierta · `0002` campañas/assignments/quórum · `0003` Postgres+events ·
`0004` Clerk · `0005` identidad de Evaluation + versionado de contenido.
