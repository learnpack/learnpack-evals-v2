# ADR-0002 — Campañas abiertas, assignments dinámicos y quórum por submissions

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto DDD:** Evaluation Orchestration

## Contexto
La realidad operativa no es "tener todos los SMEs y todas las assignments antes de empezar":
- Se arranca con los expertos disponibles y se **suman más con el tiempo**.
- Un experto puede **no cumplir** o cumplir solo parte de lo asignado → hay que **cancelar** o
  **reasignar**.

El modelo previo confundía *provisioning* (assignments) con *goal* (quórum): fijaba "N assessors
distintos por contenido al crear la campaña" y definía completitud como "todas las assignments
enviadas". Eso no soporta el aprovisionamiento incremental ni la rotación de assignments.

## Decisión
1. **`EvaluationCampaign` = agregado abierto (config + scope), no dueño transaccional de las
   assignments.** Fija `rubricVersion`, `requiredEvaluationsPerContent` (umbral) y `metadataView`.
   Ciclo `Draft → Open → Closed`. **Abrir no requiere todas las assignments.**
2. **`Assignment` = agregado propio, chico, con lifecycle** `Assigned → Opened → Submitted` |
   `Cancelled`. Reassign = cancel + nueva assignment a otro assessor. Invariante: ≤1 assignment
   activa por `(campaign, content, assessor)`; solo cancelable si no está `Submitted`.
3. **Quórum = umbral de completitud sobre submissions, no provisioning.** Un contenido está
   `Completed` cuando el nº de **assessors distintos que enviaron** una evaluación válida alcanza
   el umbral. Assignments canceladas/incompletas **no cuentan**.
4. **Completitud eventual por policy:** `EvaluationSubmitted` → contar distinct assessors →
   `≥ umbral` → `ContentEvaluationCompleted`. No es invariante transaccional de un agregado grande.

## Consecuencias
- (+) Se puede **empezar ya** con pocos expertos y sumar más sin reestructurar nada.
- (+) Cancelar/reasignar es natural; solo mueven la aguja las entregas.
- (+) `Assignment` chico → sin contención; escala bien.
- (+) La unicidad de evaluación por `(assessor, content, rubricVersion)` (contexto Evaluation)
  hace seguro contar assessors distintos.
- (−) La completitud es eventual, no inmediata (aceptable: es un proceso humano asíncrono).

## Open questions (no bloquean el MVP)
- ¿Submission sin assignment previa? (MVP: no — la assignment alimenta pendientes.)
- ¿Over-quórum? (permitido; completa al alcanzar N; extras se guardan.)
- ¿Cambiar N con la campaña abierta? (MVP: fijo.)

## Alternativas consideradas
- **Provisioning fijo (N assignments al crear) + completitud = todas enviadas** → rechazada:
  no soporta incrementalidad ni rotación; frágil ante incumplimientos.
- **Campaign posee todas las assignments (agregado grande)** → rechazada: contención y agregado
  gigante; viola "aggregates chicos".
