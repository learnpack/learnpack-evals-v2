# ADR-0005 — Identidad de `Evaluation`, versionado de contenido y anti-duplicación en el `Assignment`

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** Evaluation · Content Registry ·
Orchestration

## Contexto
El diseño previo daba a `Evaluation` la identidad `(assessor, content, rubricVersion)` con
unicidad. Dos casos la rompen:
1. **Repeticiones de la misma fuente.** Un `LLMJudge` (o incluso un humano) puede evaluar el
   mismo `(content, rubric)` **N veces** para medir dispersión (desvío, self-consistency,
   votación). La unicidad lo impide.
2. **Versiones de contenido.** El contenido evoluciona (LearnpackV1 regenera/corrige un curso).
   Es útil evaluar el mismo curso en `v1`, `v2`… con la misma rúbrica (mejora/regresión). Sin
   versión en el modelo, no se puede.

La causa de fondo: se confundió *el juicio* con *la corrida que lo produjo*, y se metió como
identidad del agregado una restricción que en realidad era anti-duplicación del MVP humano.

## Decisión
1. **`Evaluation` = un acto concreto con id propio.** Identidad = `evaluationId` (surrogate) +
   coordenadas `{assessorId, contentId (versión), rubricVersion, attempt/occurredAt}`. **Sin**
   unicidad por `(assessor, content, rubric)`: las repeticiones **conviven**.
   - La dispersión estadística se calcula por **`Assessor` concreto** (misma `SourceConfiguration`);
     cambiar la config = otro `Assessor`.
2. **Versionado de contenido de primera clase.** Cada registro de `contents` es una **versión**
   (`contentId` = versión); contenido lógico = `(generatingSystem, externalId)`; unicidad
   `(generatingSystem, externalId, version)`. MVP: `version` default `"1"`.
3. **Anti-duplicación humana en el `Assignment`, no en `Evaluation`.** ≤1 assignment activa por
   `(campaign, content, assessor)`, cumplida con **una** submission; re-enviar sobre una ya
   `Submitted` → **409**. Como el quórum se cuenta por `assignments submitted` (ADR-0002), un SME
   no puede inflar el conteo.

## Consecuencias
- (+) Correcto para `LLMJudge` (repeticiones/dispersión), calibración (desvío por `Assessor`) y
  comparación entre versiones de contenido — todo `[futuro]`, pero el modelo ya lo soporta.
- (+) El MVP humano se comporta igual (un SME evalúa cada curso una vez por campaña), pero por la
  regla del assignment, no por identidad del agregado.
- (+) `contentVersion` desde el día 1 evita rehacer migraciones al versionar.
- (−) La agregación (media/desvío) sobre repeticiones es responsabilidad de `ScoringPolicy`/
  Reporting, no de una restricción de unicidad.

## Alternativas
- **Mantener unicidad `(assessor, content, rubric)`** → rechazada: imposibilita repeticiones y
  versiones; confunde juicio con corrida.
- **Taggear `Evaluation` con `campaign_id`** → rechazada en ADR-0002 (rompe multi-campaña y la
  identidad correcta).
