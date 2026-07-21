# 02 — Discover (Big-Picture EventStorming)

> Paso 2 del DDD Starter Modelling Process. Estado: **cerrado (v0, living)**.
> Técnica: Big-Picture EventStorming. Alcance: **dominio completo** (4 fuentes +
> calibración). El MVP es el *prefijo del backbone humano* (fases 1→4 → bridge 6).

## Leyenda (convención EventStorming)

- ● **domain event** (naranja) — hecho pasado, en inglés.
- ▸ **command / actor** (azul / amarillo) — lo que dispara el evento y quién.
- ⟳ **policy** (lila) — "cuando pasó X → reacciona con Y". Motor events-first.
- ⚡ **hotspot** (rojo) — incertidumbre/decisión pendiente para Define.
- `[MVP]` / `[futuro]` — pertenencia al slice.

## Estructura: backbone + side-stream

**Evaluación** (backbone recurrente, source-agnostic, con o sin calibración) — sujeto: el
*contenido*. **Calibración** (side-stream ocasional) — sujeto: la *fuente*. La calibración
NO es un hito por el que pase toda evaluación; se ramifica. Evaluar sin calibrar es válido
(la fuente solo produce juicios con más grounding si está calibrada) → se modela como
*provenance* (`sourceCalibrationStatus`), no como prerrequisito.

---

## Backbone de evaluación

### Fase 1 — Content inventory · abre `ContentRegistered` `[MVP]`
- ▸ Admin: `RegisterContent`, `UpdateContentMetadata`
- ● `ContentRegistered` (generatingSystem, externalId, consumableUrl, internalId)
- ● `ContentMetadataUpdated` (learningObjectives, targetAudience, prerequisites)
- ⚡ ¿metadata mínima obligatoria vs. opcional?
- ⚡ ¿versionado de un mismo contenido? (futuro)
- ⚡ iframe del consumableUrl — `X-Frame-Options`/CSP (técnico → Code)

### Fase 2 — Instrument ready · abre `RubricPublished` `[MVP]`
- ▸ Admin/designer: `DefineCriterion`, `AssembleRubric`, `PublishRubric`
- ● `CriterionDefined` (text, guidance, scale 1–5, anchors, grounded_in[], eligible_sources[])
- ● `RubricAssembled` (criteria ordenados, draft)
- ● `RubricPublished` (versión *locked* → usable) — **pivotal**
- ● `RubricDeprecated` / `RubricRevised` → nueva versión (futuro)
- ⚡ **¿criteria inmutables tras publicar?** (invariante de versionado — join key de calibración)
- ⚡ ¿frameworks/dimensions/qualities como reference data desde ya, o seed en MVP?
- ⚡ eligible_sources: ¿se declara ya, o MVP asume todo → `HumanExpert`?

### Fase 3 — Evaluation in progress · abre `EvaluationRunStarted` — **dos realizaciones**
- ● `EvaluationRunStarted` (rubricVersion, contentSet, mode) — **pivotal**

**Realización humana** `[MVP]` — provisioning **abierto e incremental** (ver ADR-0002):
- ▸ Admin: `OpenCampaign` (→ `CampaignOpened`, realización humana de `EvaluationRunStarted`),
  `AssignContent`, `CancelAssignment` / `ReassignAssignment`
- ● `CampaignOpened` · `AssignmentCreated` (crea `Assignment`) · `AssignmentCancelled`
- ▸ Evaluator (SME): `OpenAssignment`, `AccessContent`, `SubmitEvaluation`
- ● `AssignmentOpened`
- ● `ContentAccessed` (abrió la url / consumió el contenido)
- ● `EvaluationSubmitted` (evaluator, content, CriterionScores[] + comments) — *workhorse,
  alta frecuencia, NO pivotal*

**Realización automática** `[futuro]` (no pasa por assignments):
- ▸ System: `RunSourceEvaluation` (batch)
- ● `MetricComputed` (`ComputedMetric` crudo — para `DeterministicVerifier`/`HybridVerifier`)
- ● `EvaluationSubmitted` (source automática; para determinística, score vía `ScoringPolicy`)

- ⟳ *`EvaluationSubmitted` → contar assessors distintos del contenido; al alcanzar el umbral
  `requiredEvaluationsPerContent` → `ContentEvaluationCompleted` (quórum por submissions, ADR-0002)*
- ⚡ **¿cuántas evaluaciones humanas por contenido?** (1 vs. N para inter-rater agreement —
  impacta calidad del golden)
- ⚡ ¿draft editable antes de `SubmitEvaluation`? (draft vs. submitted)
- ⚡ identidad simple del evaluador atada a `EvaluationSubmitted` (sin auth robusta, MVP)
- ⚡ ¿un run mezcla fuentes por-criterion? (algunos criteria determinísticos, otros LLM)
- ⚡ costos/rate-limits de `LLMJudge` (LiteLLM/OpenRouter) → Code

### Fase 4 — Aggregation · abre `ContentEvaluationCompleted` `[MVP]`
- ● `ContentEvaluationCompleted` (content, run — **relativo al run**, no global) — **pivotal**
- ⟳ *al completarse → agregar resultados*
- ● `EvaluationResultsAggregated` (agregación por-criterion vía `ScoringPolicy`)
- ⚡ **¿cómo se agregan múltiples humanos?** (media/mediana/descartar outliers/umbral de acuerdo)
- ⚡ ¿"completo" = N evaluaciones o basta 1? (liga con hotspot de fase 3)

### Fase 5 — Quality judgment · abre `QualityJudgmentPublished` `[parcial MVP: vistas admin]`
- ⟳ *resultados agregados → publicar juicio*
- ● `QualityJudgmentPublished` (content, rubricVersion, aggregatedScores, **provenance**:
  source + sourceCalibrationStatus)
- ⚡ ¿rollup por set/general además de por contenido? (promedios de admin — vistas MVP)
- ⚡ representación de la provenance (calibrada/no + contra qué referencia)

---

## Side-stream de calibración (se ramifica, no continúa la línea)

### Bridge · `GoldenReferenceEstablished` `[MVP = meta final]`
- ● `GoldenReferenceEstablished` (un `set × rubricVersion` de resultados humanos alcanzó
  estado ground-truth usable) — **pivotal**
- ⚡ **¿qué hace "usable" al golden?** (cobertura X% con ≥N evaluaciones, umbral de agreement)

### Calibración · `SourceCalibrated` `[futuro]`
- ▸ System: `RunCalibration` (requiere `GoldenReference` + resultados automáticos sobre *el
  mismo* set×rubric — que son un `EvaluationRunStarted` mode=automated apuntando al golden set)
- ● `AutomatedResultsCollectedForCalibration`
- ● `SourceCalibrated` (`CalibrationProfile` por `(Assessor, Criterion)`: agreement vs. referencia)
- ⟳ *fuente calibrada → futuros `QualityJudgment` de esa fuente llevan assessorCalibrationStatus
  actualizado*
- ⚡ métrica de agreement por criterion (correlación / Cohen's kappa / MAE) → Define/Code
- ⚡ ¿recalibrar al cambiar rubricVersion o modelo? (invalidación de calibración)

---

## Policies consolidadas (motor de evolución de estado)

1. `EvaluationSubmitted` → *check completion* → `ContentEvaluationCompleted`?
2. `ContentEvaluationCompleted` → *aggregate* → `EvaluationResultsAggregated`
3. `EvaluationResultsAggregated` → *publish* → `QualityJudgmentPublished`
4. `GoldenReferenceEstablished` (+ resultados automáticos) → *habilita* `RunCalibration`
5. `SourceCalibrated` → *actualiza provenance* de futuros `QualityJudgmentPublished`

> Estas policies son internas hoy; varias son candidatas a **integration events** salientes
> mañana (p.ej. `QualityJudgmentPublished` → API call a LearnPack o a reporting). Patrón
> "domain events → servicios externos" del modulith objetivo.

## Boundaries candidatos (insumo para 03 — Decompose)

- **Content Registry** — fase 1.
- **Rubric Authoring** — fase 2.
- **Evaluation** (core) — fases 3–5, el acto recurrente source-agnostic.
- **Evaluation Orchestration** (supporting) — campaigns/assignments; envuelve la realización
  humana de fase 3.
- **Calibration** (supporting) — side-stream.
- **Golden Dataset** — agregado con vida propia (no una vista sobre contenidos completados).

## Frontera MVP

MVP = backbone humano fases **1 → 4** desembocando en `GoldenReferenceEstablished` (bridge).
Sin `LLMJudge`, sin `SourceCalibrated`. `QualityJudgmentPublished` aparece parcialmente como
las vistas de admin (scores por curso, promedios).

## Hotspots resueltos en el cierre de Discover

- ⚡→✔ **Criteria inmutables tras publicar.** `RubricPublished` bloquea la versión; toda
  edición ⇒ nueva `rubricVersion`. Invariante de Rubric Authoring.
- ⚡→✔ **Quórum humano N=2–3 por contenido.** `ContentEvaluationCompleted` requiere ≥N
  evaluaciones; `EvaluationResultsAggregated` lleva media + inter-rater agreement.
- ⚡→✔ **Golden usable = cobertura mínima.** `GoldenDataset` es agregado con regla
  `coverage ≥ threshold` (umbral de acuerdo opcional a futuro).
- ⚡→✔ **Recalibrar al cambiar el modelo** (ver refinamiento Assessor): resuelto por
  identidad — otro config = otro `Assessor` = la calibración no transfiere.

## Refinamiento: identidad de la fuente (`Assessor`)

Se separa el *tipo* de la *instancia concreta* que produce resultados:

- `EvaluationSource` = tipo/port abstracto (HumanExpert / LLMJudge / DeterministicVerifier /
  HybridVerifier).
- **`Assessor`** = instancia concreta, identificable y versionada. Es la **clave de
  provenance y de calibración**. Para `LLMJudge` = una `SourceConfiguration`
  (model, version, sampling, promptTemplate, rubricRendering); para `HumanExpert` = el SME
  concreto; para `DeterministicVerifier` = fórmula/lib + thresholds.

Refinamientos de eventos derivados:
- `EvaluationRunStarted` y `EvaluationSubmitted` referencian el `Assessor` (no solo el mode).
- `SourceCalibrated` se keya por `(Assessor, Criterion)`.
- `QualityJudgmentPublished.provenance` incluye `assessor` + `assessorCalibrationStatus`.

MVP: el usuario evaluador ES un `Assessor` de tipo `HumanExpert` — el concepto se instancia
en su caso trivial; el slot de provenance queda abierto para `LLMJudge` futuro. Detalles de
`SourceConfiguration`, reproducibilidad y sampling → Define/Code.

## Estado y próximo paso

- Discover: **cerrado**.
- Siguiente: **03 — Decompose** — agrupar estos eventos en subdominios (boundaries
  candidatos de arriba) y preparar Strategize (core/supporting/generic).
