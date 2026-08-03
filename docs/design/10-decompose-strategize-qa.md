# 10 — Decompose & Strategize (segunda vuelta: QA interno)

> **Snapshot del diseño vigente (ago-2026)** — pasos 3–4 del DDDSMP, segunda vuelta. Congelado.
> Supersede a `03-decompose.md` y `04-strategize.md` (históricos) para todo trabajo nuevo.
> Serie: 09 → 12. *(06 — Organise sigue siendo placeholder: equipo chico, un solo dueño.)*

## Subdominios

| Subdominio | Clase | Misión | Razón para cambiar |
|---|---|---|---|
| **Evaluation Design** (ex `rubric_authoring`, ensanchado — el bucle B) | **Core** | Poseer el argumento evidencial: claims, evidence models, criteria, assembly, bindings; mintear el namespace de ids (ADR-0014); reference data del lado norma; diagnóstico de defectos; port de asistencia | Cambia qué afirmamos o cómo se reconoce |
| **Pedagogical Evaluation** (existente, reformulado) | **Core** | Ejecutar el argumento: juicio por contenido, findings, hechos de acuerdo | Cambia cómo se produce/registra un juicio |
| **Content Profiling** *(nuevo)* | Supporting (ACL interpretativo) | Paquetes crudos → evidencia canónica **citada**; adapters por `PackageFormat`; capacidades; aceptación | Cambia cómo se *lee* un formato |
| **Evaluand Registry** (ex `content_registry`, ensanchado) | Supporting | El examinado y sus productos: `GeneratorVersion`, `GenerationBrief`, `ContentVersion`+`ContentPackage` | Generador/formato/dato de origen nuevo |
| **Evaluation Studies** *(nuevo — el encargo)* | Supporting (thin deliberado) | La ronda con propósito: dataset, pinning, gate, publicación, informe del generador, comparación | Cambian las preguntas de negocio de una ronda |
| **Evaluation Orchestration** (acotado) | Supporting | Coordinar **esfuerzo humano** (campañas del panel de referencia; annotation queues) — ADR-0002/0005 intactos | Cambia cómo se organiza a las personas |
| **Golden Dataset** | Supporting | Ground truth humano + **referencia de calibración de instrumentos** (ADR-0015) | — |
| **Reporting** | Supporting-generic | Read models (ADR-0006) | — |
| **Identity** | Generic | — | — |
| **Calibration** | Supporting `[futuro]` | Calibrar assessors vs. referencia, por `(Assessor, Criterion)` | — |

## Eventos que posee cada subdominio

- **Evaluand Registry:** `GeneratorVersionRegistered` · `BriefRegistered` ·
  `ContentVersionRegistered` · `ContentMetadataUpdated` · `GeneratorArtifactRegistered`.
- **Content Profiling:** `ContentProfiled` · `ContentProfilingFailed` · `ExtractionAccepted`.
- **Evaluation Design:** `ClaimDefined` · `CriterionDefined` · `DataRequirementMinted` ·
  `InstrumentVersionPublished` · `InstrumentDefectIdentified` · `InstrumentDeprecated`.
- **Pedagogical Evaluation:** `EvaluationCompleted`/`EvaluationSubmitted` ·
  `QualityJudgmentPublished` · `FindingRaised` · `FindingDisputed` · `DisagreementDetected`.
- **Evaluation Studies:** `StudyDeclared` · `InstrumentPinned` · `StudyOpened` ·
  `StudyPublished` · `StudiesCompared`.
- **Orchestration:** `CampaignOpened` · `AssignmentCreated/Opened/Cancelled` ·
  `ContentEvaluationCompleted` (quórum humano) · `CampaignClosed`.
- **Golden Dataset:** `GoldenReferenceEstablished`.

## Flujo entre subdominios (solo eventos + queries — ARCHITECTURE §3)

```
Evaluand Registry ──ContentVersionRegistered──► Content Profiling ──ContentProfiled──► Pedagogical Evaluation
                                                                                            │
Evaluation Design ──InstrumentVersionPublished──► (Evaluation · Studies)                    │ QualityJudgmentPublished
      ▲                                                                                     ▼ FindingRaised
      │  DisagreementDetected · FindingDisputed · huecos de cobertura · oferta informal  Evaluation Studies ──► informe generador
      └──────────────────────────────── (bucle B) ◄─────────────────────────────────────────┘
Orchestration (humano) ◄──reacciona a EvaluationSubmitted── · alimenta Golden Dataset · Reporting lee por query ports
```

- **El matching** (cobertura esperada + demanda insatisfecha) es una **query compuesta** —
  Design posee la demanda (ids), Profiling la oferta (capacidades). Sin estado propio.
- **Las líneas de study disuelven la tensión resultados↔versión de instrumento:** el study fija
  instrumento + receta de briefs; la comparación es válida **dentro de una línea**; instrumento
  nuevo ⇒ línea nueva (re-evaluando baseline si se quiere comparar). Nunca se re-emiten
  resultados publicados.

## Decisiones de decomposición

1. El generador **no** es subdominio propio: vive en Evaluand Registry (config, brief y paquete
   llegan juntos en el intake; una sola razón de cambio).
2. Evaluation Design **incluye el diagnóstico** del bucle B (quien escribió el claim y sus
   explicaciones alternativas es quien elige entre ellas).
3. Evaluation Studies es subdominio **propio** (lifecycle y decisiones: componer dataset, gate,
   comparar) — ni Reporting (vistas sin decisiones) ni Orchestration (esfuerzo, no encargos).
4. **Evaluation emite los hechos de acuerdo/dispersión** (posee las evaluaciones); Studies los
   consume para el gate, Design para el diagnóstico. Sin comandos cruzados.
5. **La acumulación a nivel generador vive en Studies** (es el informe del encargo); primera
   realización con composición estilo ADR-0006.

**Deltas vs. el código del slice 1:** `rubric_authoring` → Evaluation Design ·
`content_registry` → Evaluand Registry · nuevos `content_profiling` y `evaluation_studies` ·
`evaluation`/`orchestration`/`golden_dataset`/`reporting`/`identity` quedan (orchestration
acotado al camino humano).

## Strategize — Core Domain Chart

| Subdominio | Clase | Diferenciación | Complejidad |
|---|---|---|---|
| Evaluation Design | **Core** | alta | alta |
| Pedagogical Evaluation | **Core** | alta | media-alta |
| Content Profiling | Supporting | media (potencial alto) | media |
| Evaluation Studies | Supporting | media-alta | media-baja |
| Evaluand Registry | Supporting | baja-media | baja-media |
| Orchestration | Supporting | baja-media | media |
| Golden Dataset | Supporting | media-alta | media |
| Reporting | Supporting-generic | baja | baja |
| Identity | Generic | baja | baja |
| Calibration `[futuro]` | Supporting | media (potencial alto) | alta |

**Decisiones estratégicas registradas:**

1. **El conocimiento diferenciador vive en Evaluation Design** — asciende de "Core secundario"
   (chart original) a core pleno: lo que era CRUD fino se volvió el dueño del argumento.
2. **Profiling es supporting *deliberadamente*** (el mismo movimiento que el chart original hizo
   con Calibration): habilita el determinismo, pero **sirve** al core. Un Profiling sofisticado
   es señal de sobre-inversión en traducción.
3. **Studies es supporting aunque entrega el producto**: la riqueza está en lo que transporta,
   no en su estructura. Un `Study` complicado es un smell.

**Guía de inversión:** modelo rico + invariantes + tests de dominio en Design y Evaluation ·
pragmático y fino en Studies, Profiling (**la inversión va a fixtures, no a modelo**), Registry,
Orchestration/Golden/Reporting · comprar/trivial en Identity.

**Primer incremento del slice 2:** el core de a poco con supporting mínimo — Design con pocos
claims reales · Profiling con **un** adapter (`LearnpackV1`) · Evaluation por el camino
automático mínimo · Studies thin. El camino humano no se toca hasta que el instrumento nuevo
exista; el panel de referencia (ADR-0015) usa la maquinaria existente.
</content>
