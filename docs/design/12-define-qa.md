# 12 — Define (segunda vuelta: QA interno)

> **Snapshot del diseño vigente (ago-2026)** — paso 7 del DDDSMP, segunda vuelta. Congelado.
> Supersede a `07-define.md` (histórico) para todo trabajo nuevo; este doc es **autocontenido**
> (incluye los contextos que casi no cambiaron). Serie: 09 → 12. Los nombres exactos y las
> equivalencias con la industria: `../GLOSSARY.md`.

---

## Evaluation Design (Core)

### Bounded Context Canvas

- **Propósito:** poseer el argumento evidencial: diseñar, versionar, publicar y diagnosticar
  instrumentos; mintear el namespace de ids (ADR-0014); reference data del lado norma
  (frameworks, qualities, dimensions, data requirements); asistir la autoría vía port.
- **Comandos:** `DefineClaim` · `DefineCriterion` · `AssembleInstrument` · `PublishInstrument` ·
  `ReviseInstrument` · `DeprecateInstrument` · `RegisterFramework` · `MintDataRequirement`.
  **Port de asistencia:** `RequestDrafts(purpose, frameworkIds, oferta)` → borradores.
  **Queries:** `getInstrument(version) → InstrumentSnapshot` · `getDataRequirements()`.
- **Reacciona a (bucle B):** `DisagreementDetected` · `FindingDisputed` · patrones de
  `no_evidence` · oferta informal → diagnóstico → `InstrumentDefectIdentified` → revisión.
- **Eventos:** `ClaimDefined` · `CriterionDefined` · `DataRequirementMinted` ·
  `InstrumentVersionPublished` (lleva el snapshot) · `InstrumentDefectIdentified` ·
  `InstrumentDeprecated`.

### Agregado `Instrument`

Root = `InstrumentVersion`; **posee como VOs** sus `Claim`s (enunciado + refs a qualities +
warrants + explicaciones alternativas + assembly), sus `Criterion`s y sus **bindings de
aplicabilidad** por `PackageFormat`. Referencia por id a frameworks/qualities (reference data).
Ciclo: `Draft (editable, asistible) → Published (locked) → Deprecated`.

**Invariantes:**
1. `Published` ⇒ inmutable; todo cambio ⇒ versión nueva. `claimId`/`criterionId` estables entre
   versiones (linaje del bucle B).
2. Todo claim: enunciado de una frase · ≥1 `Quality` · ≥1 warrant de framework (si es
   pedagógico) · ≥1 criterion como evidencia · regla de assembly · ≥1 explicación alternativa
   **específica del claim** (el boilerplate no cuenta; causas genéricas → taxonomía de
   diagnóstico).
3. Todo criterion: condición de pase verificable · modos de falla · requisitos de datos que
   existen en el namespace · `onMissingEvidence` ∈ {`no_evidence` (default), `fail`} — la
   **consecuencia** de la ausencia; el **hecho** lo determinan matching/profile (mecánico);
   `not_applicable` solo nace de capacidad/condicionales, jamás del criterion · ≥1 eligible
   source. *(Esta es la lectura autorizada que reconcilia ADR-0010 §5 con la derivación
   mecánica.)*
4. Publicar exige ≥1 binding (`designedFor`) + invariantes 2–3. Atómico. **No exige capacidad de
   extracción** (el diseño queda desacoplado de los adapters; readiness informa al fijar el
   study).
5. **Nada producido por asistencia entra a `Published` sin acto humano.**

**Metadata de revisión:** autor + motivo + `assistedBy` (config del asistente).

### Reference data del lado norma (agregados chicos)

- `PedagogicalFramework` — **delgado**: id · name · citations · scopeNote. El corpus de los
  asistentes NO va acá: es conocimiento de adapter, keyado por framework id.
- `Quality` / `PedagogicalDimension` — id · name · definición · `groundedIn` · `dimensionId`.
- `DataRequirement` — id · **definición obligatoria** · aliases · value domain opcional (las
  estructuras de teoría —niveles de Bloom, jerarquías de unidades— entran acá **demand-driven**,
  citando al framework; sin jerarquía de tipos aparte) · grounding opcional. Unicidad por
  revisión de diseño + lint (ADR-0014).

### Ciclo de vida de las Qualities

Cadena: `Framework ←grounded_in← Quality ←afirma-sobre← Claim ←evidenciado-por← Criterion
←requiere← DataRequirement`. Se crean en el seed + minteo **raro** en la génesis de claims. Se
usan al diseñar claims y como **eje de agregación y lectura** de informes. No aparecen en la
ejecución. Son la **columna estable del lenguaje**: claims y criteria cambian entre versiones;
los `qualityId` persisten (continuidad temática entre líneas de studies; ancla de la referencia
humana, ADR-0015).

### Port de asistencia (`DesignAssistancePort`)

Dado (propósito + framework ids + oferta del tipo), propone **borradores** de
claims/criteria/evidence models. Adapters LLM = infraestructura en este repo; corpus/prompts =
artefactos versionados del adapter, keyados por framework id. Frontera dura: borrador ≠
publicado (invariante 5). Trigger para volverse subdominio: que las sesiones de asistencia
adquieran lifecycle/estado con reglas propias.

---

## Content Profiling (Supporting — ACL interpretativo)

### Bounded Context Canvas

- **Propósito:** traducir `ContentPackage`s crudos a evidencia canónica **citada**; adapters por
  `PackageFormat`; capacidades contra el namespace; reproducibilidad por versionado de adapter;
  acto de aceptación.
- **Comandos:** `ProfileContent` · `AcceptExtraction(packageFormat, adapterVersion)` ·
  `ReprofileBatch(selección)`. **Reacciona a:** `ContentVersionRegistered` (perfilar si hay
  adapter aceptado). **Queries:** `getProfile` · `getCapabilities(packageFormat)`.
- **Eventos:** `ContentProfiled` · `ContentProfilingFailed` · `ExtractionAccepted`.

### Agregado `ContentProfile`

Root con coordenadas `{contentId, adapterVersion}`. Posee entradas canónicas
(`dataRequirementId` → valor + `EvidenceProvenance` con cita verbatim y locator) y extras
no-canónicos (marcados).

**Invariantes:**
1. Toda entrada canónica referencia un `DataRequirement` existente (Conformist) y lleva
   `EvidenceProvenance`: `declared_structured | declared_in_content | absent` — sin `inferred`,
   con cita obligatoria cuando hay valor (ADR-0009).
2. **Inmutable.** Re-perfilar con otro adapter ⇒ profile nuevo; el viejo se conserva (los
   juicios publicados lo referencian).
3. **Entrada `absent` ≠ ausencia de entrada.** Capacidad declarada + contenido sin el dato →
   `absent` explícito (→ `no_evidence`). Sin capacidad → sin entrada (→ `not_applicable` /
   demanda insatisfecha). La trampa del denominador queda bloqueada **por construcción**.
4. Extras jamás usan ids canónicos; fuera de contrato.

**El adapter es infraestructura**, no agregado: `ExtractorAdapter` por `PackageFormat`,
versionado, capacidades declaradas, **fixtures obligatorios** (la inversión de este contexto va
a fixtures, no a modelo). `ExtractionAccepted` por `(packageFormat, adapterVersion)`, repetida
en cada versión — el acto humano que habilita descartar "extracción fallida" como explicación
alternativa. Perfilado automático al registrar; **re-perfilado batch como acto explícito**
(nunca cascada silenciosa: puede invalidar evaluaciones).

---

## Evaluand Registry (Supporting)

### Bounded Context Canvas

- **Propósito:** el examinado y sus productos: `GeneratorVersion`, `GenerationBrief`,
  `ContentVersion` + `ContentPackage` + provenance de edición.
- **Comandos:** `RegisterGeneratorVersion` · `RegisterBrief` · `RegisterContentVersion` ·
  `UpdateContentMetadata` · `RegisterGeneratorArtifact`. **ACL de intake** mecánico; carga
  manual sigue existiendo. **Queries:** `getContentPackage` · `getAvailableContents(filtros)` ·
  `getGeneratorVersion` · `getBrief`.
- **Eventos:** `GeneratorVersionRegistered` · `BriefRegistered` · `ContentVersionRegistered` ·
  `ContentMetadataUpdated` · `GeneratorArtifactRegistered`.

### Agregados (tres chicos)

- **`GeneratorVersion`** — identidad **declarada** del examinado:
  `{id, name, version, metadata libre opcional, createdAt}`. Identidad inmutable; un generador
  realmente distinto ⇒ registro nuevo (disciplina declarativa — no enforceable). El **drift
  silencioso es indetectable desde adentro**; "drift no registrado" es causa estándar de la
  taxonomía de diagnóstico. Campos de config se promueven del blob **solo cuando algo los
  consuma**.
- **`GenerationBrief`** — inmutable, con identidad (`briefId`) referenciada por los
  `ContentVersion`: la clave del **diseño pareado**. Contenido lean: texto libre + campos
  tipados que las task variables consuman. Brief ausente = registrado ausente.
- **`EducationalContent`/`ContentVersion`** — unicidad `(PackageFormat, externalId, version)`
  (ADR-0005 intacto) · `ContentMetadata` (ADR-0001 intacto) · `ContentPackage` (VO de artefactos
  `{kind, locator, formato}`, `kind` **abierto**) · `briefId` · `generatorVersionId` (nullable →
  `unknown`, excluido de acumulación) · provenance de edición
  `pure | human_edited | unknown`.

`PackageFormat` (formato → elige adapter) y `GeneratorVersion` (examinado → acumula claims) son
**dos ejes distintos**; el `ContentVersion` lleva ambos. *(Trigger: si una plataforma emitiera
varios formatos compartiendo externalIds, nacería un `SourceSystem`.)*

---

## Pedagogical Evaluation (Core)

### Bounded Context Canvas

- **Propósito:** ejecutar el argumento sobre un contenido; derivar findings; publicar el juicio
  (claims con estatus); emitir hechos crudos de acuerdo.
- **Comandos:** `EvaluateContent(contentId, instrumentVersion, assessorId)` (automático) ·
  `SubmitEvaluation` (humano — ADR-0005 intacto) · `DisputeFinding`. **Queries batch:**
  `getJudgments` · `getFindings` · `getEvaluations`.
- **Eventos:** `EvaluationCompleted`/`EvaluationSubmitted` · `QualityJudgmentPublished` ·
  `FindingRaised` · `DisagreementDetected` · `FindingDisputed`.

### Agregado `Evaluation`

Un **acto**. Root con `evaluationId` propio; coordenadas `{assessorId, contentId,
instrumentVersion, adapterVersion del profile, occurredAt/attempt}`. Repeticiones permitidas;
anti-duplicación humana en el `Assignment` (ADR-0005). Posee el `EvaluationResult` = un
`CriterionScore` (tri-estado) por criterion + `ComputedMetric`s crudos (que admiten valores
estructurados).

**Invariantes:**
1. **Cobertura exacta tri-estado:** un outcome por cada criterion del `instrumentVersion` — ni
   falta ni sobra. *(Supersede la invariante "score ∈ [1,5]" del 07 histórico; el 1–5 pervive
   solo en el panel de referencia, ADR-0015.)*
2. **Derivación mecánica:** sin capacidad o condicional excluido → `not_applicable`; entrada
   `absent` del profile → `no_evidence` (o `fail` si el criterion lo declara); `scored` exige
   **cita**. El assessor solo juzga lo juzgable.
3. Inmutable al completarse. Referencias válidas (instrumento publicado, profile existente,
   assessor registrado).
4. **Cadena de provenance completa:** `{instrumentVersion, adapterVersion, assessorId,
   contentVersion}` — sin excepciones.

**Eventos por evaluación, no por criterion** (outcomes como filas; sin consumidor por-criterion
independiente). **Umbrales de acuerdo en el assembly** (Design): Evaluation mide siempre y emite
`DisagreementDetected` al cruzarse el umbral. **`ScoringPolicy` está disuelta**: mapeo
métrica→desenlace = condición de pase del criterion; agregación = assembly + ADR-0011.

### `QualityJudgment` y `Finding` — derivados, inmutables

- `QualityJudgment` por `(contentVersion, instrumentVersion)`: claims con estatus + perfil por
  criterion + cobertura + métricas de acuerdo. Compartido entre studies que fijaron el mismo
  instrumento (espeja "una evaluación satisface varias campañas", ADR-0005).
- `Finding`: `{claimId, criterionId, cita, modo de falla → sugerencia}`. `FindingDisputed` =
  hecho registrado *sobre* un finding, consumido por Design.

**Participación humana (ADR-0015):** el modo *panel de referencia* (qualities directas, sin
profile — `Rubric v1` estabilizada como instrumento de referencia) queda **fuera** de la
ejecución de instrumentos; el modo *assessor/verificador* trabaja sobre el profile (annotation
queues muestreadas). El prerequisito de profile en la ejecución se mantiene.

---

## Evaluation Studies (Supporting — thin deliberado)

### Bounded Context Canvas

- **Propósito:** la ronda con propósito: dataset, pinning, gate de confiabilidad, publicación,
  informe del generador, comparación entre rondas.
- **Comandos:** `DeclareStudy(propósito, aserciones deseadas)` · `PinInstrument` ·
  `ComposeDataset(briefIds/contentIds)` · `OpenStudy` · `PublishStudy` · `CompareStudies(a,b)`.
  **Reacciona a:** `QualityJudgmentPublished` · `FindingRaised` · `DisagreementDetected` ·
  `ContentEvaluationCompleted` (humano). **Queries:** `getStudyReport` · `getComparison` ·
  readiness.
- **Eventos:** `StudyDeclared` · `InstrumentPinned` · `StudyOpened` · `StudyPublished` ·
  `StudiesCompared`.

### Agregado `EvaluationStudy`

Root; posee propósito, pin, **receta** (briefIds) y **dataset materializado** (contentIds) como
VOs (`EvaluationDataset`). Ciclo: `Declared (instrumento pendiente — el estado del arranque en
frío) → Prepared → Open → Published`.

**Invariantes:**
1. Instrumento fijado **una vez**, antes de abrir, inmutable después. Readiness **informa, no
   bloquea**.
2. Dataset fijo al abrir (el camino humano puede llenarlo incrementalmente vía campañas).
3. `Published` ⇒ informe inmutable, jamás re-emitido. Publicar es **acto humano**.
4. El informe siempre lleva **cobertura y caveats** (evidencia insuficiente, desacuerdos sin
   resolver, exclusiones `unknown`, adapters sin aceptar). Publicar con caveats es legítimo y
   visible; **publicar en silencio, imposible**.

### `StudyReport` — derivado, inmutable

Por contenido: claims con estatus. A nivel generador: **por cada claim, la distribución de
estatus a través del dataset** + **patrones condicionados por task variables** ("objetivos vagos
*solo* en cursos introductorios"). Nunca agregado cross-claim (ADR-0011 rige). Claims de grano
generador explícitos con regla de acumulación propia = `[futuro]`, definidos en el instrumento.
`CompareStudies` valida compatibilidad (mismo `instrumentVersion` + datasets pareados por
briefs) → `StudiesComparison`; la "línea" es agrupamiento derivado, no entidad.

---

## Contextos que casi no cambian (autocontenido — ajustes sobre el 07 histórico)

- **Evaluation Orchestration (Supporting):** coordina **esfuerzo humano**. `EvaluationCampaign`
  (abierta e incremental, ADR-0002: fija versión de instrumento, umbral
  `requiredEvaluationsPerContent`, `metadataView`; no posee assignments transaccionalmente) +
  `Assignment` (lifecycle `Assigned → Opened → Submitted | Cancelled`; ≤1 activa por
  `(campaign, content, assessor)`; re-enviar sobre `Submitted` → 409, ADR-0005). Quórum por
  umbral de submissions (policy sobre `EvaluationSubmitted`). Usos: campañas del **panel de
  referencia** (capa 1) y **annotation queues** del modo verificador (capa 2). Nunca recibe
  comandos de Studies.
- **Golden Dataset (Supporting):** agregado por `(contentSet, versión del instrumento de
  referencia)`; cada contenido con ≥N evaluaciones humanas; `usable` cuando
  `coverage ≥ threshold`; policy sobre `ContentEvaluationCompleted` →
  `GoldenReferenceEstablished`. **Rol adicional (ADR-0015): referencia de calibración de
  instrumentos** — los coeficientes de validez por claim se computan contra él.
- **Reporting (Supporting-generic):** composición vía query ports + agregación en Python
  (ADR-0006); inter-rater por criterion (dispersión simple); repeticiones colapsan a la más
  reciente por assessor. **Sin score agregado único** (ADR-0011 — `overall_average`/
  `global_average` se retiran); vistas agrupadas por quality/dimensión permitidas como
  presentación.
- **Identity (Generic):** usuarios/roles; provee `assessorId`. Sin cambios (ADR-0004/0007/0008).

---

## Registro de decisiones y deferrals

Los 28 puntos de decisión de esta vuelta (DP1–DP28), la revisión de coherencia pre-cierre y sus
resoluciones están razonados en los ADRs 0009–0015 y resumidos arriba en cada canvas. Piezas
transversales:

- **Claim afirma *sobre* una Quality; el claim media entre criterion y quality** (en `Rubric v1`
  la relación criterion↔dimensión es directa — es el instrumento de referencia).
- **Sin biblioteca de claims:** portabilidad por copia con linaje (`claimId` estable). Reuso
  sobre un tipo nuevo = **versión nueva que agrega el binding**.
- **`TaskModelBinding`**: lado instrumento = aplicabilidad + task variables + criteria
  condicionales; el "dónde vive cada dato en el formato" es del adapter (Profiling).
- **`EvaluationRun` está fundido en `EvaluationStudy`**; el "compuesto/preset" no necesita
  nombre: **es el `Instrument`**.

**Deferrals explícitos a Code (deliberados — no inventar sin plan):** el esquema operativo del
**assembly** (qué significa "suficiente": criteria scored, % pass, mínimo de assessors, umbral
de acuerdo) · la forma concreta de las **métricas de validez por claim** (ADR-0015) · la
realización de las **annotation queues** · la forma concreta de value domains estructurados.

**Primer incremento — thin/no:** implementación del port de asistencia (el modelo queda; los
adapters LLM no) · perfilado de `GeneratorArtifact` (registrar sí, extraer no) ·
`StudiesCompared` (necesita dos rondas) · eventos de draft por edición (con el evento de
publicación alcanza).
</content>
