> ⚠️ **SNAPSHOT HISTÓRICO (jul-2026)** — diseño que produjo el slice 1 (MVP humano). El diseño
> vigente es la serie **`09-align-discover-qa.md` … `12-define-qa.md`** (QA interno). **No usar
> este doc como fuente para código nuevo.**

# 03 — Decompose

> Paso 3 del DDD Starter Modelling Process. Estado: **cerrado (v0, living)**.
> Objetivo: agrupar los domain events de Discover en subdominios de baja acoplamiento y
> alta cohesión. En el monolito modular, cada subdominio ≈ un módulo.

## Subdominios y eventos que posee cada uno

### Pedagogical Evaluation
Producir juicios de calidad con provenance a partir de `(Content, Rubric, Assessor)`.
- Eventos: `EvaluationRunStarted` (parte automática), `MetricComputed`, `EvaluationSubmitted`,
  `ContentEvaluationCompleted`, `EvaluationResultsAggregated`, `QualityJudgmentPublished`.
- Conceptos: `Evaluation`, `EvaluationSource`/`Assessor`, `ComputedMetric`, `ScoringPolicy`,
  `CriterionScore`, `EvaluationResult`.
- Depende de: Rubric Authoring (rubrics publicadas), Content Registry (targets + metadata).

### Rubric Authoring
El modelo pedagógico encodeado + versionado de instrumentos.
- Eventos: `CriterionDefined`, `RubricAssembled`, `RubricPublished`, `RubricRevised`,
  `RubricDeprecated`.
- Conceptos: `PedagogicalFramework`, `PedagogicalDimension`, `Quality`, `EvaluationCriterion`
  (grounding N:M, `eligible_sources`, anchors), `Rubric` (versionada, inmutable al publicar).
- Reference data: frameworks/dimensions/qualities (versionadas, no hardcodeadas).

### Evaluation Orchestration  *(supporting)*
Workflow humano de evaluación (abierto e incremental — ver ADR-0002).
- Eventos: `CampaignOpened`, `AssignmentCreated`, `AssignmentOpened`, `AssignmentCancelled`,
  `ContentEvaluationCompleted`, `CampaignClosed`.
- Conceptos: `EvaluationCampaign` (abierta; no dueña transaccional de assignments), `Assignment`
  (lifecycle propio), quórum por umbral de submissions.
- Dispara runs humanos de Pedagogical Evaluation y detecta completitud.

### Golden Dataset  *(supporting)*
Curar el ground truth humano.
- Eventos: `GoldenReferenceEstablished`.
- Reglas: cada contenido incluido alcanzó su quórum (`ContentEvaluationCompleted`, de
  Orchestration); `coverage ≥ threshold` para "usable".
- Se alimenta de resultados humanos de Pedagogical Evaluation.

### Calibration  *(supporting)*
Medir/ajustar `Assessor` automáticos vs. la referencia.
- Eventos: `AutomatedResultsCollectedForCalibration`, `SourceCalibrated`.
- Conceptos: `CalibrationProfile` keyado por `(Assessor, Criterion)`.
- Depende de: Golden Dataset + resultados automáticos de Pedagogical Evaluation. `[futuro]`

### Content Registry  *(supporting → generic)*
Registrar contenido + metadata + provenance del generador.
- Eventos: `ContentRegistered`, `ContentMetadataUpdated`.
- Conceptos: `EducationalContent`/`Course`, `GeneratingSystem`, `ContentMetadata`.

### Reporting / Projections  *(supporting-generic)*
Read models sobre domain events.
- Vistas: pendientes por evaluador, scores por curso, promedios (por curso, por evaluador,
  global). `[parcial MVP]`

### Genéricos
- **Identity & Access** — usuarios/evaluadores/admin, auth. `[MVP: id simple]`
- **Notifications** — avisos de assignment, etc. `[futuro]`
- **Localization** — i18n EN/ES. `[futuro]`

## Mapa de dependencias (anticipo de Connect)

```
Identity  ← (todos)
Content Registry ──► Pedagogical Evaluation ◄── Rubric Authoring
Evaluation Orchestration ──dispara──► Pedagogical Evaluation (runs humanos)
Pedagogical Evaluation ──resultados humanos──► Golden Dataset
Golden Dataset + resultados automáticos ──► Calibration
Pedagogical Evaluation / Orchestration ──eventos──► Reporting
```

Estas flechas son los flujos de eventos/API permitidos entre módulos del monolito.

## Próximo paso
**04 — Strategize** (clasificación core/supporting/generic + Core Domain Chart).
