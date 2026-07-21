# Ubiquitous Language — Glossary (v0, living document)

> Convención: los **términos del dominio y del código van en inglés**; las glosas y la
> discusión, en español. Este glosario es *vivo*: cambia a medida que aprendemos en
> Discover / Define. Cada término es candidato a `class` / `value object` / `event`.

## Content axis — qué se evalúa

- **EducationalContent** (aka `ContentArtifact`) — lo que se evalúa. Concepto raíz del
  target de evaluación.
- **Course** — un tipo concreto de `EducationalContent` (p.ej. un curso LearnPack).
- **GeneratingSystem** — el sistema que generó el contenido (p.ej. `LearnpackV1`).
- **ContentMetadata** — colección **abierta y tipada** de `MetadataEntry` usada como *referencia*
  de evaluación; validada contra un `MetadataSchema` ligado al `GeneratingSystem`/tipo. El
  dominio no referencia keys concretas. MVP: schema `learnpack-v1` =
  `{learningObjectives, targetAudience, prerequisites}`. Ver `adr/0001-open-content-metadata.md`.
- **MetadataEntry** — `{key, value, valueType}`.
- **MetadataSchema** — declara keys permitidas/requeridas + tipos por `GeneratingSystem`/tipo
  (reference data).

## Criteria axis — qué se mide (el "qué")

- **PedagogicalFramework** — teoría de referencia que *fundamenta* (grounding), no
  contiene. Set inicial: Merrill (First Principles), Biggs (Constructive Alignment),
  Revised Bloom (Anderson & Krathwohl), SOLO, Schmidt (Coherence), Learning Progressions.
- **PedagogicalDimension** — agrupación de qualities (las "dimensiones" del equipo).
- **Quality** — cualidad pedagógica granular, evaluable. `grounded_in` uno o varios
  `PedagogicalFramework` (relación N:M). *(Naming abierto: quizá `PedagogicalAttribute`.)*
- **EvaluationCriterion** — operacionalización de una `Quality`/`Dimension` en algo
  medible: enunciado, guía, escala 1–5, anchors (qué es 1, qué es 5). **Cita** su grounding
  (N:M); no lo contiene. Declara sus `eligible_sources`.
- **Rubric** (aka `EvaluationInstrument`) — conjunto ordenado y **versionado** de criteria.
  Unidad intercambiable. MVP = `LearnPack Pedagogical Rubric v1` (5 criteria).

## Source axis — cómo se produce el juicio (el "cómo")

- **EvaluationSource** — **port** único (el *tipo* de fuente); produce el juicio. *("Evaluator"
  en uso coloquial / el usuario del MVP = un `Assessor` de tipo `HumanExpert`.)* Adapters:
  - **HumanExpert** — SME interno/externo.
  - **LLMJudge** — juez basado en LLM sobre una rubric.
  - **DeterministicVerifier** — fórmulas / índices / reglas (readability, cohesion,
    Bloom-tagging, alineación por embeddings, chequeos de presencia/orden).
  - **HybridVerifier** — fusión determinístico + LLM (la "Hybrid Norm").
- **Assessor** — la *instancia concreta, identificable y versionada* de una
  `EvaluationSource` que realmente produce resultados (el "quién/qué exactamente", vs. el
  "qué clase" del tipo). Es la **clave de provenance y de calibración**.
  - `HumanExpert` → un SME concreto (con expertise profile). *(En el MVP, el usuario que
    evalúa ES un `Assessor` de tipo `HumanExpert`.)*
  - `LLMJudge` → una `SourceConfiguration`.
  - `DeterministicVerifier` → fórmula/librería + versión + thresholds.
- **SourceConfiguration** — la config que define a un `Assessor` automático de tipo
  `LLMJudge`: `{provider/model, modelVersion, sampling/temperature, promptTemplate version,
  rubricRenderingStrategy, toolConfig}`. Cualquier cambio ⇒ *otro* `Assessor` (la
  calibración no transfiere: invalidación por identidad).
- **eligible_sources** — relación de compatibilidad `Criterion` ↔ `EvaluationSource`:
  no todo criterion admite toda fuente (algunos son computables, otros requieren juicio).

## Evaluation & results

- **Evaluation** — el acto: una `EvaluationSource` evalúa un target usando una `Rubric`.
- **ComputedMetric** (aka `Signal`) — **medición cruda** producida por fuentes
  determinísticas/híbridas (p.ej. FK grade level, índice de cohesión, coseno de
  alineación). *No es un score*; se mapea a score vía `ScoringPolicy`.
- **ScoringPolicy** — cómo se mapea `ComputedMetric` → score (mapeo + umbral/referencia),
  y cómo se **agregan/componen** varios scores/results.
- **CriterionScore** — score 1–5 por criterion (+ `Comment` opcional).
- **EvaluationResult** — el conjunto de `CriterionScore` (+ comentarios) de una `Evaluation`.
- **QualityJudgment** — el juicio de calidad publicado sobre un contenido: scores agregados
  por criterion + **provenance** (`assessor` + `assessorCalibrationStatus`). Evento:
  `QualityJudgmentPublished`.

## Orchestration & calibration (supporting)

- **EvaluationRun** — un esfuerzo de evaluación sobre un `(contentSet, rubricVersion)` por un
  `mode` (human / automated). Evento: `EvaluationRunStarted`.
- **EvaluationCampaign** — realización humana de un `EvaluationRun`, **abierta e incremental**
  (config + scope): fija `rubricVersion`, `requiredEvaluationsPerContent` (umbral de completitud,
  no provisioning) y `metadataView`. Se abre con los assessors que haya y suma más; **no posee
  las assignments transaccionalmente**. Ver ADR-0002.
- **Assignment** — invitación a un `Assessor` a evaluar un `Content` en una campaña; agregado
  chico con lifecycle `Assigned → Opened → Submitted | Cancelled`. Reassign = cancel + nueva.
- **quorum / requiredEvaluationsPerContent** — umbral de completitud: un contenido está
  `Completed` cuando el nº de **assessors distintos que enviaron** una evaluación válida alcanza
  el umbral. Las assignments canceladas/incompletas no cuentan.
- **GoldenDataset** — agregado de referencia etiquetado por humanos, con **regla propia**:
  `usable` cuando alcanza una cobertura mínima (`coverage ≥ threshold`); cada contenido
  requiere un quórum de **N=2–3** evaluaciones humanas.
- **Calibration** — ajuste/validación de fuentes automáticas contra la referencia humana,
  keyada por **`(Assessor, Criterion)`** (no por el tipo abstracto): se calibra una
  configuración concreta, criterion por criterion.
- **CalibrationProfile** (aka `SourceCalibration`) — output de la calibración: el agreement
  de un `Assessor` con la referencia, por criterion. *Cualifica* (no habilita) las
  evaluaciones futuras de ese `Assessor`, vía `assessorCalibrationStatus` en la provenance
  del `QualityJudgment`.

## Cross-cutting

- **DomainEvent** — hecho pasado del dominio; medio por el que evoluciona el estado
  (events-first). Ej.: `ContentRegistered`, `RubricPublished`, `EvaluationRunStarted`,
  `AssignmentCreated`, `AssignmentCancelled`, `MetricComputed`, `EvaluationSubmitted`,
  `ContentEvaluationCompleted`, `QualityJudgmentPublished`, `GoldenReferenceEstablished`,
  `SourceCalibrated`.
- **Localization** — i18n de la UI (EN/ES). Preocupación del modelo objetivo; MVP = EN.

## Combinación de frameworks — dos niveles (no confundir)

- **Design-time synthesis** — una rubric cuyos criteria están `grounded_in` varios
  frameworks (el caso del MVP: 5 preguntas destilan 6 marcos).
- **Runtime composition** — varias rubrics/lentes evaluadas y agregadas vía `ScoringPolicy`
  para obtener sub-scores comparables por lente.
