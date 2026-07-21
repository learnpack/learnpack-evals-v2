# 07 — Define (opción B: MVP slice)

> Paso 7 del DDD Starter Modelling Process. Estado: **en curso**.
> Alcance (opción B): solo lo que el MVP toca — la rebanada humana. Contextos:
> Rubric Authoring · Content Registry · Evaluation (humano) · Evaluation Orchestration ·
> Golden Dataset · Reporting · Identity. Cada uno: Bounded Context Canvas + Aggregate Design
> Canvas. Las decisiones se toman sin cerrar puertas al modelo objetivo (01–05).

Orden de definición: **Rubric Authoring** (insumo del evaluador) → Evaluation (humano) →
Content Registry → Orchestration → Golden Dataset → Reporting → Identity.

---

## Rubric Authoring

### Bounded Context Canvas
- **Propósito:** definir y versionar los instrumentos de evaluación (`Rubric`) y el modelo
  pedagógico que los fundamenta (frameworks → dimensions → qualities → criteria, con grounding
  y `eligible_sources`); garantizar la inmutabilidad de una rubric publicada.
- **Clasificación:** Core (secundario). Modelo rico; workflow/CRUD fino.
- **Inbound** — Comandos: `DefineCriterion`, `AssembleRubric`, `PublishRubric`,
  `ReviseRubric`, `DeprecateRubric`. Query: `getRubric(rubricVersion) → RubricSnapshot`.
- **Outbound** — Eventos: `CriterionDefined`, `RubricAssembled`, `RubricPublished` (lleva el
  `RubricSnapshot`), `RubricRevised`, `RubricDeprecated`.
- **Published Language `RubricSnapshot`:**
  `{ rubricId, version, criteria: [{ criterionId, prompt, guidance, scaleMin:1, scaleMax:5,
  anchorLow, anchorHigh, eligibleSources[], groundedIn[] }] }`.
- **Ubiquitous language:** PedagogicalFramework, PedagogicalDimension, Quality,
  EvaluationCriterion, Rubric, rubricVersion, anchors, eligible_sources.
- **Open questions:** estado `Draft` explícito en MVP vs seed directo a `Published`; pesos por
  criterion (MVP: sin pesos, media simple); naming `Quality` vs `PedagogicalAttribute`.

### Aggregate Design Canvas — `Rubric`
- **Descripción:** versión ordenada e inmutable de criteria para evaluar contenido. Root =
  `Rubric` (una versión); **posee** sus `Criterion` (VOs). **Referencia por id** a
  `PedagogicalFramework`/`Quality` (reference data, fuera del boundary).
- **Ciclo de vida:** `Draft → Published (→ Deprecated)`. MVP: seed directo a `Published`.
- **Invariantes:**
  1. `Published` ⇒ versión inmutable; criteria congelados. Cambio ⇒ nueva `rubricVersion`.
  2. ≥1 criterion; cada criterion: escala 1–5, ambos anchors (1 y 5), `prompt` + `guidance`
     presentes, `eligible_sources` ≥1.
  3. `criterionId` único dentro de la rubric.
  4. `rubricVersion` estable y global (join key de evaluación y calibración).
- **Enforcement:** síncrono; `PublishRubric` atómico (agregado completo = un límite
  transaccional). Sin corrective policies.
- **Comandos → eventos:** `DefineCriterion→CriterionDefined`, `AssembleRubric→RubricAssembled`,
  `PublishRubric→RubricPublished`, `ReviseRubric→RubricRevised`,
  `DeprecateRubric→RubricDeprecated`.
- **Tamaño:** chico (v1 = 5 criteria).
- **Realización MVP:** sin UI de autoría. `Rubric v1` = *seed data* de una versión `Published`
  y locked. Comandos de autoría `[futuro]`. El evaluador consume un `RubricSnapshot v1`
  read-only.

### Reference data (agregados chicos, seed en MVP)
`PedagogicalFramework`, `PedagogicalDimension`, `Quality` — CRUD mínimo; en el MVP se siembran.
Los criteria los referencian por id (`groundedIn[]`, dimensión/quality).

### Rubric v1 — instanciada (seed en `seed/rubric-v1.json`)
5 criteria (uno por dimensión; cada criterion colapsa las qualities de su dimensión en una
pregunta 1–5). Anchors genéricos (1 = not at all/very low, 5 = fully/very high). Scope: calidad
pedagógica del **contenido** (objetivos, lecciones, coherencia, progresión); **excluye
presentación y ecosistema**.

| # | criterionId | dimensión | groundedIn |
|---|---|---|---|
| 1 | `objectives-quality` | Quality and soundness of objectives | Biggs · Revised Bloom · SOLO |
| 2 | `constructive-alignment` | Constructive alignment (objective↔content) | Biggs · Revised Bloom |
| 3 | `instructional-design` | Instructional design of the lesson | Merrill |
| 4 | `inter-lesson-coherence` | Coherence and continuity between lessons | Schmidt |
| 5 | `learning-progression` | Learning progression | Learning progressions · SOLO · Merrill · Schmidt · Revised Bloom |

Observaciones que confirman/afinan el modelo:
- **Criterion ↔ Dimension es 1:1 en v1** (score por dimensión, colapsando qualities). El modelo
  ya lo admite (Criterion operacionaliza Quality *o* Dimension).
- **Grounding a nivel Quality, agregado al Criterion** (`Criterion.groundedIn` = unión de los
  frameworks de las qualities de su dimensión). Las 21 qualities + 5 dimensions + 6 frameworks
  son reference data sembrable.
- **Anchors genéricos** (mismos 1/5). Open question: ¿anchors por-criterion a futuro?
- **`eligible_sources` v1 = [HumanExpert]** en los 5. Candidatos a automatización futura
  (informativo): 1–2 → Bloom-tagging/embeddings; 4 → Coh-Metrix; etc.
- **Metadata (corregido):** los evaluadores reciben el **curso completo** (todas las lecciones);
  el `lessonPlan` era de una versión previa y se descarta. La metadata del contenido se modela
  **abierta/extensible** (no campos fijos) — ver ADR-0001 y Content Registry.

---

## Evaluation (parte humana, MVP)

### Bounded Context Canvas
- **Propósito:** producir y persistir el juicio de un `Assessor` sobre un contenido usando una
  rubric — el acto core. MVP: solo `HumanExpert`.
- **Clasificación:** Core.
- **Inbound** — Comando: `SubmitEvaluation(assessorId, contentId, rubricVersion, scores[])`.
  Queries: `getRubric(rubricVersion)`, `getContentMetadata(contentId)`.
- **Outbound** — Evento: `EvaluationSubmitted(assessorId, contentId, rubricVersion,
  EvaluationResult, mode=human)`. No publica `ContentEvaluationCompleted` (ver refinamiento).
- **Ubiquitous language:** Evaluation, EvaluationResult, CriterionScore, Assessor, provenance.

### Aggregate Design Canvas — `Evaluation`
- **Descripción:** registro de un `Assessor` puntuando un contenido contra una `rubricVersion`.
  Root = `Evaluation`; contiene un `EvaluationResult` (los `CriterionScore` + comments).
- **Ciclo de vida (MVP):** `Submitted`. (Draft/InProgress = `[futuro]`.)
- **Invariantes:**
  1. Cobertura exacta: un `CriterionScore` por cada `criterionId` de la `rubricVersion` (ni
     falta ni sobra).
  2. score ∈ [1,5] entero; comment opcional.
  3. Referencias válidas: `rubricVersion` publicada, `contentId` registrado, `assessorId`.
  4. Unicidad: ≤1 `Evaluation` por `(assessorId, contentId, rubricVersion)`. Re-submit =
     bloqueado o update → open question.
  5. Inmutable una vez `Submitted` (MVP).
- **Límite de consistencia:** `Evaluation` + `EvaluationResult` = unidad transaccional; submit
  atómico.
- **Comando → evento:** `SubmitEvaluation → EvaluationSubmitted`.
- **Corrective policies:** validación síncrona; rubric/criteria inválidos → rechazo.
- **Throughput/tamaño:** bajo, sin concurrencia; agregado chico (5 scores).
- **Provenance:** `EvaluationSubmitted` lleva el `Assessor` (HumanExpert id), `mode=human`.

> **Refinamiento vs Discover:** `ContentEvaluationCompleted` lo emite **Orchestration** (que
> conoce el quórum: creó N assignments por contenido y detecta completitud al recibir los
> `EvaluationSubmitted`), no el core `Evaluation`. La agregación cross-evaluador (media +
> inter-rater) queda como proyección de Reporting/Golden.

### Realización MVP
`SubmitEvaluation` → append de fila(s) (`EvaluationSubmitted`): una fila por evaluación con
columnas de score+comment por criterion (simple para Sheets y para reporting).

---

## Content Registry (supporting → generic)

### Bounded Context Canvas
- **Propósito:** registrar contenido evaluable + su metadata (abierta/extensible) + provenance del
  sistema generador; servir metadata a los consumidores.
- **Inbound** — Comandos: `RegisterContent`, `UpdateContentMetadata`. Queries:
  `getContentMetadata(contentId)`, `getContentSnapshot(contentId)`. ACL: ingesta LearnPack
  (MVP: carga manual → ACL trivial).
- **Outbound** — Eventos: `ContentRegistered`, `ContentMetadataUpdated`. DTO:
  `ContentSnapshot { contentId, generatingSystem, externalId, consumableUrl, metadata: MetadataEntry[] }`.

### Aggregate Design Canvas — `EducationalContent`
- Root = Content; posee su `ContentMetadata` (colección abierta de `MetadataEntry`).
- **Invariantes:** único `(generatingSystem, externalId)`; `consumableUrl` presente; metadata
  válida contra el `MetadataSchema` de su tipo (si existe). El dominio no referencia keys
  concretas (ver ADR-0001).
- **Comandos → eventos:** `RegisterContent→ContentRegistered`,
  `UpdateContentMetadata→ContentMetadataUpdated`.
- **Realización MVP:** schema sembrado `learnpack-v1 = {learningObjectives, targetAudience,
  prerequisites}`; metadata a mano; sin lessonPlan (los evaluadores reciben el curso completo).

## Evaluation Orchestration (supporting) · refinado (ver ADR-0002)

### Bounded Context Canvas
- **Propósito:** orquestar el esfuerzo humano de forma **abierta e incremental** — campañas que
  se abren con los assessors que haya y suman más con el tiempo; assignments con lifecycle
  (cancelar/reasignar); detectar completitud por **umbral de submissions**; presentar la
  metadata al evaluador.
- **Inbound** — Comandos: `OpenCampaign`, `AssignContent`, `CancelAssignment`,
  `ReassignAssignment`, `CloseCampaign`. Reacciona a: `EvaluationSubmitted`. Queries:
  `getPendingAssignments(assessorId)`, `getCampaignProgress(campaignId)`.
- **Outbound** — Eventos: `CampaignOpened`, `AssignmentCreated`, `AssignmentOpened`,
  `AssignmentCancelled`, `ContentEvaluationCompleted`, `CampaignClosed`.

### Aggregate `EvaluationCampaign` (config + scope; open-ended)
- **Descripción:** configuración y alcance de un esfuerzo de evaluación. **No** posee las
  assignments transaccionalmente.
- **Invariantes:** `rubricVersion` publicada y fija; `requiredEvaluationsPerContent` (umbral N,
  típ. 2–3) fijo; `contentSet` no vacío para abrir; `metadataView`.
- **Ciclo de vida:** `Draft → Open (acepta assignments y submissions de a poco) → Closed`.
  **Abrir NO requiere tener todas las assignments.**

### Aggregate `Assignment` (chico, lifecycle propio)
- **Descripción:** invitación a un `Assessor` a evaluar un `Content` dentro de una campaña.
- **Estados:** `Assigned → Opened → Submitted` · `Cancelled`. (Reassign = `Cancel` + nuevo
  `Assign` a otro assessor.)
- **Invariantes:** a lo sumo una assignment **activa** (no cancelada) por
  `(campaign, content, assessor)`; solo se cancela si no está `Submitted`.
- **Comandos → eventos:** `AssignContent→AssignmentCreated`, `OpenAssignment→AssignmentOpened`,
  `CancelAssignment→AssignmentCancelled`. Al oír `EvaluationSubmitted` (contexto Evaluation) la
  assignment pasa a `Submitted`.

### Quórum = umbral de completitud sobre submissions (no provisioning)
- Un contenido está `Completed` cuando el nº de **assessors distintos que enviaron** una
  evaluación válida alcanza `requiredEvaluationsPerContent`. **Las assignments canceladas o
  incompletas no afectan el conteo**; solo cuentan las submissions.
- **Policy:** `EvaluationSubmitted` → cuenta distinct assessors del contenido; `≥ umbral` →
  `ContentEvaluationCompleted`. Reasignaciones funcionan solas (cuenta quien envía).
- **Consistencia:** conteo/completitud **eventual** (policy sobre eventos), no invariante
  transaccional de un agregado grande.

### Open questions
- ¿submission sin assignment previa? (MVP: no — la assignment alimenta la lista de pendientes).
- ¿over-quórum? (permitido; completa al alcanzar N; extras se guardan).
- ¿cambiar N con la campaña abierta? (MVP: fijo).

### Realización MVP
Hojas: `campaigns`, `assignments` (con `status`), `evaluations`. Pendientes y progreso = queries
sobre esas hojas. `ContentEvaluationCompleted` puede ser vista computada (distinct submitted ≥ N).

## Golden Dataset (supporting)

### Bounded Context Canvas
- **Propósito:** curar el ground truth humano — acumular resultados, aplicar cobertura, declarar
  usable.
- **Inbound** — Reacciona a: `ContentEvaluationCompleted`. Queries: `getGoldenReference(rubricVersion)`,
  `getCoverage`.
- **Outbound** — Evento: `GoldenReferenceEstablished`.

### Aggregate Design Canvas — `GoldenDataset` (por `(contentSet, rubricVersion)`)
- **Invariantes:** cada contenido incluido con ≥N evaluaciones humanas; `usable` cuando
  `coverage ≥ threshold`.
- **Policy:** `ContentEvaluationCompleted` → cubre contenido; `coverage ≥ threshold` →
  `GoldenReferenceEstablished`.
- **Realización MVP:** thin; `threshold` configurable (p.ej. ~50 cursos o ≥X%).

## Reporting / Projections (supporting-generic)

- **Propósito:** read models (CQRS read side): pendientes, scores por curso, promedios (curso /
  evaluador / global), inter-rater agreement.
- **Inbound** — Suscribe: `EvaluationSubmitted`, `AssignmentCreated`, `AssignmentCancelled`,
  `ContentEvaluationCompleted`, `GoldenReferenceEstablished`. Sin agregado propio.
- **Realización MVP:** proyecciones desde las filas (Sheets). La agregación cross-evaluador
  (media + inter-rater) vive acá.

## Identity & Access (generic)

- **Propósito:** usuarios (admin, evaluadores) + identificación simple; provee `assessorId`.
- **Realización MVP:** identificación simple (link/id conocido; flag de admin), sin auth robusta.
  La identidad del `HumanExpert` (`Assessor`) se origina acá.

## Modelado de metadata variable (ADR-0001)

Dos concerns separados para no contaminar el dominio:
1. **Metadata intrínseca del contenido** (Content Registry): colección **abierta y tipada**
   (`MetadataEntry`) validada contra un `MetadataSchema` por `GeneratingSystem`/tipo (reference
   data, no código). → "varía por tipo de contenido".
2. **Vista de la campaña** (Orchestration): `EvaluationCampaign.metadataView` = qué keys
   presentar/requerir al evaluador. → "varía por campaña".

El dominio nunca ramifica sobre keys concretas; la presentación vive en adapters/UI. Detalle y
alternativas en `adr/0001-open-content-metadata.md`.

## Estado
Define del **MVP slice: completo** (Rubric Authoring · Evaluation · Content Registry ·
Orchestration · Golden Dataset · Reporting · Identity). Próximo: **08 — Code** (plan de
implementación del MVP + ADRs).
