# Ubiquitous Language — Glossary (v0, living document)

> Convención: los **términos del dominio y del código van en inglés**; las glosas y la
> discusión, en español. Este glosario es *vivo*: cambia a medida que aprendemos en
> Discover / Define. Cada término es candidato a `class` / `value object` / `event`.

## Content axis — qué se evalúa

- **EducationalContent** (aka `ContentArtifact`) — lo que se evalúa. Un contenido registrado es
  **una versión concreta** (identificada por `contentId`); el contenido *lógico* es la agrupación
  `(PackageFormat, externalId)`. El target de evaluación es siempre una versión.
- **Course** — un tipo concreto de `EducationalContent` (p.ej. un curso LearnPack).
- **ContentVersion** — versión de un contenido lógico. Permite evaluar el mismo curso en `v1`,
  `v2`… (mejora/regresión). Unicidad lógica: `(PackageFormat, externalId, version)`. MVP:
  default `"1"`. Referencia `generatorVersionId` (nullable → `unknown`) y `briefId`, y lleva
  **provenance de edición**: `pure | human_edited | unknown`.
- **PackageFormat** *(antes `GeneratingSystem`; el código del slice 1 conserva
  `generating_system` hasta su migración)* — la **convención del paquete** que un extraction
  adapter sabe leer (p.ej. `LearnpackV1`). Eje de *formato*: selecciona el adapter y hace de
  namespace del `externalId` (ADR-0005). Distinto del eje de *examinado* (`GeneratorVersion`);
  pueden divergir — el generador v2.3 y el v2.4 pueden emitir ambos paquetes `LearnpackV1`.
  *(Trigger anotado: si una plataforma emitiera varios formatos compartiendo externalIds,
  nacería un `SourceSystem` separado.)*
- **GeneratorVersion** *(antes `GeneratorConfiguration`)* — la **identidad declarada del
  examinado**: `{id, name, version, metadata libre opcional}`. **Inmutable**; un generador
  realmente distinto ⇒ registro nuevo. Es la clave de acumulación de los claims a nivel
  generador (ADR-0013) — simetría de *rol* con `SourceConfiguration`, no de mecanismo: acá la
  identidad es **declarativa e incomprobable** (el generador está fuera del sistema), por eso no
  hay campos de config obligatorios (se promueven del blob a campos tipados solo cuando algo los
  consuma). `unknown` permitido: contenido válido para juicios por contenido, **excluido** de la
  acumulación a nivel generador. El drift silencioso es indetectable desde adentro — disciplina
  de proceso, y causa registrada en la taxonomía de diagnóstico del bucle B.
- **ContentPackage** — el work product **completo** que entrega el generador para un contenido:
  VO de artefactos `{kind, locator, formato}` con vocabulario de `kind` **abierto** (consumable,
  manifest, knowledge-graph, item-bank, … — sin enum en el dominio). El registro captura el
  paquete, no solo una `consumable_url`; los artefactos internos suelen ser la mejor evidencia
  (`declared_structured`, ADR-0009). Puede haber artefactos **a nivel generador** (compartidos
  entre contenidos; se registran ya, se perfilan cuando un claim los necesite).
- **GenerationBrief** — el encargo de generación: **agregado propio, inmutable, con identidad**
  (`briefId`) que los `ContentVersion` referencian — la clave del **diseño pareado** entre
  `GeneratorVersion`s (mismos briefs, productos nuevos). Contenido lean: texto libre + solo los
  campos tipados que las task variables consuman (demand-driven). Brief ausente = registrado
  ausente (limita la comparación pareada y deja explicaciones alternativas sin descartar).
- **ContentMetadata** — colección **abierta y tipada** de `MetadataEntry` usada como *referencia*
  de evaluación; validada contra un `MetadataSchema` ligado al `PackageFormat`/tipo. El
  dominio no referencia keys concretas. MVP: schema `learnpack-v1` =
  `{learningObjectives, targetAudience, prerequisites}`. Ver `adr/0001-open-content-metadata.md`.
- **MetadataEntry** — `{key, value, valueType}`.
- **MetadataSchema** — declara keys permitidas/requeridas + tipos por `PackageFormat`/tipo
  (reference data).
- **ContentProfile** — representación **canónica** de lo que un `ContentPackage` contiene
  pedagógicamente, producida por un extraction adapter por `PackageFormat`. Datos keyados por
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
  lo contiene. Declara sus `eligible_sources`, los **datos que requiere** (ids, ADR-0014) y
  `onMissingEvidence` ∈ {`no_evidence` (default), `fail`} — la **consecuencia** de la ausencia
  del dato; el **hecho** lo determinan matching/profile (mecánico, nunca el assessor), y
  `not_applicable` solo nace de capacidad/condicionales.
  ADR-0010 define su forma: **condición de pase verificable + modos de falla enumerados**,
  desenlace `scored (pass/fail) | not_applicable | no_evidence | not_assessed` (ADR-0018) — no
  una escala de apreciación. (La escala 1–5 sobrevive en `Rubric v1`, que **no se migra**: es el instrumento
  de referencia de la calibración — ADR-0015.)
- **Rubric** (aka `EvaluationInstrument`) — conjunto ordenado y **versionado** de criteria.
  Unidad intercambiable. MVP = `LearnPack Pedagogical Rubric v1` (5 criteria).
  Génesis (ADR-0012): un instrumento nace del **propósito + tipo de contenido** (designed-for);
  los frameworks **fundamentan** (warrant), no originan. Reusarlo sobre otro tipo = acto
  deliberado, re-ligando el task model.
  **Rol de `Rubric v1` (ADR-0015):** no se migra a la forma ADR-0010 — se **estabiliza como el
  instrumento de referencia** de la calibración (capa 1): elicitación holística por dimensión
  (1–5) para el panel humano. Su estabilidad es una feature: una referencia que cambia no es
  referencia.

## Evaluation design — el argumento evidencial (ECD-lite, ADRs 0012–0014)

- **Instrument / InstrumentVersion** — el **agregado central del diseño**: una versión del
  argumento evidencial completo. Root = `InstrumentVersion`; **posee como VOs** sus `Claim`s,
  sus `Criterion`s y sus **bindings de aplicabilidad** por `PackageFormat` (designed-for).
  Ciclo: `Draft (editable, asistible) → Published (locked) → Deprecated`; publicar es atómico y
  **humano**. `Published` ⇒ inmutable — todo cambio ⇒ versión nueva; `claimId`/`criterionId`
  estables entre versiones (linaje). **Es "el compuesto"**: con el instrument poseyendo
  claims + criteria + sufficiency + bindings, el viejo "preset de rúbricas" no necesita nombre
  propio (DP28). Relación con `Rubric`: término del slice 1 que el Instrument supersede;
  `Rubric v1` pervive como instrumento de referencia (ADR-0015).
- **Claim** — afirmación evaluable sobre la calidad, de **una frase**, con: evidencia requerida,
  warrant (framework) y explicaciones alternativas. **Dos granos:** sobre un contenido y sobre el
  **generador** (acumulada a través de contenidos — el producto central del QA interno). Estatus
  evidencial: `soportado | refutado | evidencia insuficiente`. Los findings se organizan **bajo
  el claim que comprometen**. El diseño corre hacia atrás: claims → evidencia → observables →
  requisitos de extracción (ADR-0013).
- **EvidenceModel** — para cada claim: qué evidencia lo soporta/refuta, qué observables la
  constituyen y qué **datos requiere** (ahí se mintean los ids — ADR-0014; el "diccionario" es
  una vista generada, no un artefacto).
- **Sufficiency** *(antes `Assembly` — el término ECD; renombrada por claridad en el plan de
  código, `design/13-code-qa.md` §7)* — cuánta evidencia basta **por claim**, decidido en
  diseño; expresada con la taxonomía psicométrica de modelos de decisión: `conjunctive`
  (default) · `existential` · `m_of_n`. Lo **compensatorio (pesos/promedios/umbral de puntos)
  está prohibido** — ADR-0011 un nivel arriba. El cuantificador fino ("al menos 2 de 3…")
  pertenece a la `pass_condition` del criterion, no a esta regla. En el camino automático
  reemplaza la noción de quórum (el quórum humano de ADR-0002 sigue rigiendo las campañas con
  evaluadores humanos).
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
  regresión / comparación). Lifecycle: `Declared` (propósito, instrumento pendiente) →
  `Prepared` (instrumento **fijado** una vez, inmutable; set compuesto) → `Open` (set fijo) →
  `Published` (acto humano; informe inmutable, jamás re-emitido, siempre con cobertura y
  caveats). La comparación entre rondas (`CompareStudies`) exige mismo `instrumentVersion` +
  sets pareados por briefs; la "línea" es agrupamiento derivado, no entidad.
  **Mapeo de industria:** ver §"Equivalencias con la industria de evals".
- **EvaluationDataset** *(antes `EvaluationSet` — rename final por alineación con el término
  universal)* — VO del study (no agregado): la **receta** (briefIds — la clave reutilizable del
  diseño pareado) + el **dataset materializado** (contentIds, fijado al abrir), con composición
  estratificada según qué claims necesitan qué variedad (content module, ADR-0013). Sus ítems
  son contenidos, sin *expected output* (eso lo aporta la referencia humana, ADR-0015). Distinto
  del `GoldenDataset` (que es de *resultados humanos*).

## Source axis — cómo se produce el juicio (el "cómo")

- **EvaluationSource** — **port** único (el *tipo* de fuente); produce el juicio. Taxonomía
  (ADR-0016): **`human | automated`** — la única distinción con diferencia estructural real
  (los humanos entran por assignments/UI; los automatizados por config + ejecución). *(Los
  tipos anteriores `LLMJudge`/`DeterministicVerifier`/`HybridVerifier` eran un espectro, no
  identidades: todo assessor automatizado es código que, por criterion, usa el mecanismo
  idóneo — con o sin LLM adentro. Ver tabla de equivalencias.)*
  - **human** — SME interno/externo. **Dos modos de participación (ADR-0015):** *panel de
    referencia* — juzga qualities directamente leyendo el contenido, sin profile (capa 1 de
    calibración; elicitación holística, fuera del alcance de ADR-0010) · *assessor/verificador
    dentro del instrumento* — trabaja sobre el profile, verificando outcomes citados (capa 2;
    prerequisito de profile intacto).
  - **automated** — artefacto de software **modular y versionado** con un mapeo interno
    `criterion → ejecutor` (código puro, fórmulas/índices, llamadas a LLM — detalle interno,
    nunca identidad). **Declara un instrumento target**: se debe a sus criteria — relación
    instrumento 1 → 0..N assessors automatizados; **cobertura declarada** validada al
    registrarlo: mapeo ∪ **abstenciones** == criteria del target, sin solapamiento
    (ADR-0018; lo abstenido deriva a `not_assessed`). Los humanos no están ligados a
    instrumentos.
- **Assessor** — la *instancia concreta, identificable y versionada* de una
  `EvaluationSource` que realmente produce resultados (el "quién/qué exactamente", vs. el
  "qué clase" del tipo). Es la **clave de provenance y de calibración**.
  - `human` → un SME concreto (con expertise profile). *(En el MVP, el usuario que evalúa ES
    un `Assessor` humano.)*
  - `automated` → una `SourceConfiguration` `{name, version, instrumentVersionId, config}`.
- **SourceConfiguration** — la config que define a un `Assessor` automatizado (ADR-0016).
  Cualquier cambio — código, mapeo, modelo, prompt, threshold interno — ⇒ *otro* `Assessor`
  (la calibración no transfiere: invalidación por identidad).
- **eligible_sources** — relación de compatibilidad `Criterion` ↔ `EvaluationSource`, valores
  `{human, automated}`: no todo criterion admite toda fuente.

## Evaluation & results

- **Evaluation** — un **acto** concreto de evaluación (no un hecho único): un `Assessor` evalúa
  una versión de contenido usando un `InstrumentVersion` (legacy: `Rubric v1`). Identidad =
  **id propio** (`evaluationId`) + coordenadas `{assessorId, contentId (versión),
  instrumentVersion (antes rubricVersion), adapterVersion del profile, occurredAt/attempt}`.
  **No** hay unicidad por coordenadas: se permiten **repeticiones** del mismo `Assessor` (p.ej.
  un assessor automatizado corrido N veces para medir dispersión). La anti-duplicación humana vive en el
  `Assignment`, no acá. Ver ADR-0005 — **intacto**. Los desenlaces
  `not_applicable`/`no_evidence`/`not_assessed` se **derivan mecánicamente** (matching +
  profile + abstenciones registradas del assessor, ADR-0018), nunca los decide el assessor en
  runtime; `scored` exige cita.
- **ComputedMetric** (aka `Signal`) — **medición cruda** producida por fuentes
  determinísticas/híbridas (p.ej. FK grade level, índice de cohesión, coseno de alineación,
  distribución de niveles de Bloom). **Admite valores estructurados** (distribuciones, listas),
  no solo escalares; forma concreta demand-driven. *No es un desenlace*: se mapea a
  `CriterionScore` vía la **condición de pase del criterion** (ADR-0010 — los umbrales son
  parte del evidence rule).
- **ScoringPolicy** — **disuelta** (Define slice 2): su mitad "mapear `ComputedMetric` →
  desenlace" vive ahora en la **condición de pase del criterion** (los umbrales son parte del
  evidence rule, ADR-0010); su mitad "agregar/componer" vive en la **sufficiency** por claim
  (ADR-0013), bajo la prohibición de ADR-0011. La entrada se conserva como trazabilidad; el
  código del slice 1 puede referirla hasta su migración.
- **CriterionScore** — el desenlace de un criterion sobre un contenido (+ `Comment` opcional).
  Forma ADR-0010 + ADR-0018: `scored (pass/fail) | not_applicable | no_evidence | not_assessed`,
  **con la cita que lo sostiene** (solo `scored` la exige). Los tres estados no-scored son tres
  causas con tres remedios: sin capacidad/condicional (`not_applicable`) · dato ausente del
  contenido (`no_evidence`) · assessor sin ejecutor para el criterion (`not_assessed`). (El
  score 1–5 sobrevive en el flujo del **panel de referencia** — `Rubric v1`, ADR-0015.)
- **EvaluationResult** — el conjunto de `CriterionScore` (+ comentarios) de una `Evaluation`.
- **QualityJudgment** — el juicio de calidad publicado sobre un contenido: **perfil por
  criterion** (nunca un score agregado único, ADR-0011) + **cobertura** (evaluados / no aplican /
  sin evidencia / sin assessor capaz — ADR-0018) + **provenance** (`assessor` +
  `assessorCalibrationStatus`). Con ECD-lite
  (ADR-0013) se comunica como **claims con estatus evidencial** y findings bajo cada claim.
  Evento: `QualityJudgmentPublished`.
- **Finding** — hallazgo derivado de un criterion no cumplido: qué falló, la **cita**, y la
  sugerencia que sale del modo de falla declarado (la falla *es* la sugerencia). **Inmutable y
  derivado** de la evaluación; las impugnaciones son hechos separados *sobre* un finding, que
  alimentan la mejora del instrumento — no el score.

## Orchestration & calibration (supporting)

- **EvaluationRun** — **fundido en `EvaluationStudy`** (Define slice 2, DP28): el run era el
  mecanismo sin porqué; el study es el porqué con mecanismo. `EvaluationRunStarted` muere; los
  eventos de study lo reemplazan. Entrada conservada como trazabilidad; el código del slice 1
  puede referirlo hasta su migración.
- **EvaluationCampaign** — realización humana de un `EvaluationRun`, **abierta e incremental**
  (config + scope): fija `rubricVersion`, `requiredEvaluationsPerContent` (umbral de completitud,
  no provisioning) y `metadataView`. Se abre con los assessors que haya y suma más; **no posee
  las assignments transaccionalmente**. Ver ADR-0002.
- **Assignment** — invitación a un `Assessor` a evaluar un `Content` en una campaña; agregado
  chico con lifecycle `Assigned → Opened → Submitted | Cancelled`. Reassign = cancel + nueva.
  **Es la unidad de anti-duplicación humana:** ≤1 assignment activa por
  `(campaign, content, assessor)`, cumplida con **una** submission (re-enviar sobre una ya
  `Submitted` → 409). Ver ADR-0005.
- **quorum / requiredEvaluationsPerContent** — umbral de completitud **del camino humano**
  (ADR-0002): un contenido está `Completed` cuando el nº de **assessors distintos que enviaron**
  una evaluación válida alcanza el umbral. Las assignments canceladas/incompletas no cuentan.
  En el camino automático "completo" = **cobertura**, y la suficiencia de evidencia por claim la
  fija la **sufficiency** (ADR-0013).
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
  (events-first). Ej. (modelo slice 2): `GeneratorVersionRegistered` · `BriefRegistered` ·
  `ContentVersionRegistered` · `ContentProfiled` / `ContentProfilingFailed` ·
  `ExtractionAccepted` · `InstrumentVersionPublished` · `InstrumentDefectIdentified` ·
  `EvaluationCompleted` / `EvaluationSubmitted` · `QualityJudgmentPublished` · `FindingRaised` ·
  `FindingDisputed` · `DisagreementDetected` · `StudyOpened` / `StudyPublished` /
  `StudiesCompared` · camino humano: `AssignmentCreated`/`AssignmentCancelled`,
  `ContentEvaluationCompleted` (quórum) · `GoldenReferenceEstablished` · `SourceCalibrated`
  `[futuro]`. Muertos por Define: `EvaluationRunStarted` (DP28) · `MetricComputed` como evento
  (DP19: es fila, no evento) · `RubricPublished` → `InstrumentVersionPublished`.
- **Localization** — i18n de la UI (EN/ES). Preocupación del modelo objetivo; MVP = EN.

## Equivalencias con la industria de evals

> El lenguaje ubicuo es nuestro; la alineación con la industria importa en los **bordes**
> (onboarding, tooling, integraciones). **Disciplina:** en docs y código de dominio, los
> términos de industria **no nombran conceptos de dominio** — aparecen solo en adapters (ACL,
> `ARCHITECTURE.md` §3) y en esta tabla. Regla de adopción: término estándar solo cuando no
> colapsa una distinción que pagamos por mantener.

| Nuestro término | Industria | Nota |
|---|---|---|
| `EvaluationStudy` | *experiment* (LangSmith/Braintrust/Phoenix/Langfuse offline) · *evaluation run* (MLflow) | "experiment" es ambiguo entre ecosistemas (unidad vs. **contenedor** en MLflow); el study es más rico: propósito, gate, publicación, camino humano, nivel generador |
| línea de studies | *benchmark interno* / historial vs. baseline | comparación válida solo dentro de la línea (pinning) |
| `EvaluationDataset` | *dataset* | adoptado — término universal |
| `GoldenDataset` | *golden dataset* | ya alineado (referencia humana) |
| `Criterion` **+** `Assessor` ejecutándolo | *scorer* (Braintrust/MLflow) · *evaluator* (LangSmith/Azure) · *metric* (DeepEval/Ragas) · *grader* (OpenAI) · *assertion* (promptfoo) | **cinco nombres, ningún estándar** — y todos fusionan el *qué* con el *quién*; nuestra separación es la precisión que no cedemos |
| `Assessor` automatizado (ADR-0016) | *LLM-as-judge* · *scorer/evaluator* automatizado · nuestros ex `LLMJudge`/`DeterministicVerifier`/`HybridVerifier` | el mecanismo (con o sin LLM) es detalle interno del assessor; `Assessor` (instancia versionada con instrumento target) es más preciso — la industria no versiona jueces |
| `Sufficiency` | *evidence assembly / accumulation* (ECD) · agregación de assertions (promptfoo et al.) | acumulación simple y explícita (ADR-0013), taxonomía conjunctive/existential/m_of_n; lo compensatorio de la industria está prohibido (ADR-0011) |
| `CriterionScore` | *score* (el "objeto universal" de Langfuse) | el nuestro lleva cita + desenlace de estados discretos (`scored`/`not_applicable`/`no_evidence`/`not_assessed`) |
| `Evaluation` (el acto) | ≈ *trace con scores* / fila de un dataset run | su "run" es a nivel dataset — **falso amigo, no adoptar** |
| colas de verificación (capa 2, ADR-0015) | *annotation queue* | **adoptado** como término de realización |
| `StudiesComparison` | *experiment comparison* / *regression testing* | dentro de una línea |
| `QualityJudgment` / `StudyReport` | *evaluation results* / scorecard | claims con estatus — sin análogo directo |
| (observabilidad, infra) | *trace* | vocabulario de infraestructura (Langfuse/MLflow); sin colisión con el dominio |

## Combinación de frameworks — dos niveles (no confundir)

- **Design-time synthesis** — un instrumento cuyos claims/criteria están `grounded_in` varios
  frameworks (el caso de `Rubric v1`: 5 preguntas destilan 6 marcos; en el modelo de claims, el
  warrant de cada claim cita sus frameworks).
- **Runtime composition** — *(superado por Define slice 2)*: el "compuesto de rubrics/lentes"
  ya no existe como concepto aparte — **el `Instrument` es el compuesto** (posee claims +
  criteria + sufficiency + bindings, DP28), y la agregación la fija su **sufficiency**, nunca
  un `ScoringPolicy` (disuelta) ni un score único (ADR-0011).
