# Ubiquitous Language — Glossary (v0, living document)

> Convención: los **términos del dominio y del código van en inglés**; las glosas y la
> discusión, en español. Este glosario es *vivo*: cambia a medida que aprendemos en
> Discover / Define. Cada término es candidato a `class` / `value object` / `event`.

## Content axis — qué se evalúa

- **EducationalContent** (aka `ContentArtifact`) — lo que se evalúa. Un contenido registrado es
  **una versión concreta** (identificada por `contentId`); el contenido *lógico* es la agrupación
  `(GeneratingSystem, externalId)`. El target de evaluación es siempre una versión.
- **Course** — un tipo concreto de `EducationalContent` (p.ej. un curso LearnPack).
- **ContentVersion** — versión de un contenido lógico. Permite evaluar el mismo curso en `v1`,
  `v2`… (mejora/regresión). Unicidad lógica: `(GeneratingSystem, externalId, version)`. MVP:
  default `"1"`.
- **GeneratingSystem** — el sistema que generó el contenido (p.ej. `LearnpackV1`). Como *formato*
  identifica el tipo de contenido (adapter de extracción); como **examinado** del QA se versiona
  vía `GeneratorConfiguration`.
- **GeneratorConfiguration** — la configuración **versionada e identificable** del
  `GeneratingSystem` como examinado: modelo base, prompts, pipeline. Cambio de configuración ⇒
  **otro examinado** ⇒ los claims acumulados no transfieren — simetría exacta con
  `SourceConfiguration`/`Assessor`. Es la clave de acumulación de los claims a nivel generador
  (ADR-0013). Incluye registrar si el contenido es salida pura o con **edición humana**
  (provenance de edición). *(Naming abierto.)*
- **ContentPackage** — el work product **completo** que entrega el generador para un contenido:
  artefactos consumibles (lecciones, ejercicios) **y artefactos internos** (manifests con
  objetivos, knowledge graph de prerequisitos, banco de ítems). El registro captura el paquete,
  no solo una `consumable_url`; los artefactos internos suelen ser la mejor evidencia
  (`declared_structured`, ADR-0009). Puede haber artefactos **a nivel generador** (compartidos
  entre contenidos). *(Naming abierto.)*
- **GenerationBrief** — el encargo con el que el generador produjo un contenido (prompt,
  syllabus, parámetros, audiencia). Habilita: comparación **pareada** entre versiones del
  generador (mismos briefs, productos distintos), variables del task model ("se pidió
  introductorio") y descarte de explicaciones alternativas ("no tiene prerequisitos porque no se
  pidieron"). *(Naming abierto.)*
- **ContentMetadata** — colección **abierta y tipada** de `MetadataEntry` usada como *referencia*
  de evaluación; validada contra un `MetadataSchema` ligado al `GeneratingSystem`/tipo. El
  dominio no referencia keys concretas. MVP: schema `learnpack-v1` =
  `{learningObjectives, targetAudience, prerequisites}`. Ver `adr/0001-open-content-metadata.md`.
- **MetadataEntry** — `{key, value, valueType}`.
- **MetadataSchema** — declara keys permitidas/requeridas + tipos por `GeneratingSystem`/tipo
  (reference data).
- **ContentProfile** — representación **canónica** de lo que un `ContentPackage` contiene
  pedagógicamente, producida por un extraction adapter por `GeneratingSystem`. Datos keyados por
  los ids de datos de ADR-0014, cada uno con su `EvidenceProvenance`. **Se persiste** (reusable
  entre instrumentos) y lleva la **versión del adapter** en su provenance. Los criteria operan
  sobre el profile, nunca sobre el contenido crudo.
- **EvidenceProvenance** — origen de cada dato extraído:
  `declared_structured | declared_in_content | absent`, con **locator** (cita verbatim +
  ubicación). No existe `inferred`: el motor no completa lo que el contenido no dice (ADR-0009).
  Distinta de la provenance del `Assessor`: aquella dice *quién juzgó*; esta, *de dónde salió el
  dato juzgado*.

## Criteria axis — qué se mide (el "qué")

- **PedagogicalFramework** — teoría de referencia que *fundamenta* (grounding), no
  contiene. Set inicial: Merrill (First Principles), Biggs (Constructive Alignment),
  Revised Bloom (Anderson & Krathwohl), SOLO, Schmidt (Coherence), Learning Progressions.
- **PedagogicalDimension** — agrupación de qualities (las "dimensiones" del equipo).
- **Quality** — cualidad pedagógica granular, evaluable: la **variable del modelo del examinado**
  (ECD). Los `Claim`s afirman *sobre* ella. `grounded_in` uno o varios `PedagogicalFramework`
  (relación N:M). Es la **columna estable del lenguaje**: claims y criteria cambian entre
  versiones de instrumento; los `qualityId` persisten y dan continuidad temática entre líneas de
  studies. *(Naming abierto: quizá `PedagogicalAttribute`.)*
- **EvaluationCriterion** — la unidad de juicio verificable. Con claims (ADR-0013), el criterion
  **evidencia claims** y alcanza la `Quality` a través de ellos — el claim media; en `Rubric v1`
  (legacy) la operacionalización criterion↔dimension es directa. **Cita** su grounding (N:M); no
  lo contiene. Declara sus `eligible_sources` y los **datos que requiere** (ids, ADR-0014).
  ADR-0010 define su forma: **condición de pase verificable + modos de falla enumerados**,
  desenlace tri-estado (`scored (pass/fail) | not_applicable | no_evidence`) — no una escala de
  apreciación. (La escala 1–5 con anchors sobrevive solo en `Rubric v1`; ver ADR-0010 §Alcance y
  migración.)
- **Rubric** (aka `EvaluationInstrument`) — conjunto ordenado y **versionado** de criteria.
  Unidad intercambiable. MVP = `LearnPack Pedagogical Rubric v1` (5 criteria).
  Génesis (ADR-0012): un instrumento nace del **propósito + tipo de contenido** (designed-for);
  los frameworks **fundamentan** (warrant), no originan. Reusarlo sobre otro tipo = acto
  deliberado, re-ligando el task model.

## Evaluation design — el argumento evidencial (ECD-lite, ADRs 0012–0014)

- **Claim** — afirmación evaluable sobre la calidad, de **una frase**, con: evidencia requerida,
  warrant (framework) y explicaciones alternativas. **Dos granos:** sobre un contenido y sobre el
  **generador** (acumulada a través de contenidos — el producto central del QA interno). Estatus
  evidencial: `soportado | refutado | evidencia insuficiente`. Los findings se organizan **bajo
  el claim que comprometen**. El diseño corre hacia atrás: claims → evidencia → observables →
  requisitos de extracción (ADR-0013).
- **EvidenceModel** — para cada claim: qué evidencia lo soporta/refuta, qué observables la
  constituyen y qué **datos requiere** (ahí se mintean los ids — ADR-0014; el "diccionario" es
  una vista generada, no un artefacto).
- **Assembly** — cuánta evidencia basta **por claim**, decidido en diseño. En el camino
  automático reemplaza la noción de quórum (el quórum humano de ADR-0002 sigue rigiendo las
  campañas con evaluadores humanos).
- **AlternativeExplanation** — enumeradas *por adelantado* por claim: qué produciría la misma
  observación sin que el claim aplique (extracción fallida, formato atípico, criterion ambiguo).
  Formaliza el diagnóstico del bucle de mejora y el canal de impugnación.
- **TaskModelBinding** — la ligadura **por tipo de contenido**, del lado del instrumento:
  aplicabilidad declarada (`designedFor`) + **task variables** que condicionan el juicio (nivel
  esperado, audiencia — la "referencia contextual" del `ScoringPolicy`) + criteria condicionales.
  El **dónde vive cada dato en el formato** NO está acá: es el mapeo del adapter de extracción
  (Content Profiling). Claims y evidence models son portables; solo el binding se rehace por
  tipo — reusar un instrumento sobre un tipo nuevo = **nueva versión que agrega el binding**.
- **EvaluationStudy** — el **encargo**: una ronda de evaluación con propósito (inicial /
  regresión / comparación), que liga claims + instrumento + dataset + informe, con un acto de
  **publicación** ("estos resultados son confiables"). Comparable entre rondas (regresión
  pedagógica del generador) si el instrumento y los briefs se mantienen. *(Naming abierto:
  `Study` / `Round` / `Encargo`.)*
- **EvaluationSet** — el dataset de contenidos de un study, **fijado** (conjunto o receta), con
  composición estratificada según qué claims necesitan qué variedad (content module, ADR-0013).
  Distinto del `GoldenDataset` (que es de *resultados humanos*). *(Naming abierto.)*

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

- **Evaluation** — un **acto** concreto de evaluación (no un hecho único): un `Assessor` evalúa
  una versión de contenido usando una `Rubric`. Identidad = **id propio** (`evaluationId`) +
  coordenadas `{assessorId, contentId (versión), rubricVersion, occurredAt/attempt}`. **No** hay
  unicidad por `(assessor, content, rubric)`: se permiten **repeticiones** del mismo `Assessor`
  sobre el mismo `(content, rubric)` (p.ej. un `LLMJudge` corrido N veces para medir dispersión).
  La anti-duplicación humana del MVP vive en el `Assignment`, no acá. Ver ADR-0005.
- **ComputedMetric** (aka `Signal`) — **medición cruda** producida por fuentes
  determinísticas/híbridas (p.ej. FK grade level, índice de cohesión, coseno de
  alineación). *No es un score*; se mapea a score vía `ScoringPolicy`.
- **ScoringPolicy** — cómo se mapea `ComputedMetric` → score (mapeo + umbral/referencia),
  y cómo se **agregan/componen** varios scores/results.
- **CriterionScore** — el desenlace de un criterion sobre un contenido (+ `Comment` opcional).
  Forma ADR-0010: tri-estado `scored (pass/fail) | not_applicable | no_evidence`, **con la cita
  que lo sostiene**. (El score 1–5 sobrevive solo en el flujo humano de `Rubric v1`.)
- **EvaluationResult** — el conjunto de `CriterionScore` (+ comentarios) de una `Evaluation`.
- **QualityJudgment** — el juicio de calidad publicado sobre un contenido: **perfil por
  criterion** (nunca un score agregado único, ADR-0011) + **cobertura** (evaluados / no aplican /
  sin evidencia) + **provenance** (`assessor` + `assessorCalibrationStatus`). Con ECD-lite
  (ADR-0013) se comunica como **claims con estatus evidencial** y findings bajo cada claim.
  Evento: `QualityJudgmentPublished`.
- **Finding** — hallazgo derivado de un criterion no cumplido: qué falló, la **cita**, y la
  sugerencia que sale del modo de falla declarado (la falla *es* la sugerencia). **Inmutable y
  derivado** de la evaluación; las impugnaciones son hechos separados *sobre* un finding, que
  alimentan la mejora del instrumento — no el score.

## Orchestration & calibration (supporting)

- **EvaluationRun** — un esfuerzo de evaluación sobre un `(contentSet, rubricVersion)` por un
  `mode` (human / automated). Evento: `EvaluationRunStarted`.
- **EvaluationCampaign** — realización humana de un `EvaluationRun`, **abierta e incremental**
  (config + scope): fija `rubricVersion`, `requiredEvaluationsPerContent` (umbral de completitud,
  no provisioning) y `metadataView`. Se abre con los assessors que haya y suma más; **no posee
  las assignments transaccionalmente**. Ver ADR-0002.
- **Assignment** — invitación a un `Assessor` a evaluar un `Content` en una campaña; agregado
  chico con lifecycle `Assigned → Opened → Submitted | Cancelled`. Reassign = cancel + nueva.
  **Es la unidad de anti-duplicación humana:** ≤1 assignment activa por
  `(campaign, content, assessor)`, cumplida con **una** submission (re-enviar sobre una ya
  `Submitted` → 409). Ver ADR-0005.
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
