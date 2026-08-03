# 11 — Connect (segunda vuelta: QA interno)

> **Snapshot del diseño vigente (ago-2026)** — paso 5 del DDDSMP, segunda vuelta. Congelado.
> Supersede a `05-connect.md` (histórico) para todo trabajo nuevo. Serie: 09 → 12.

## Context map

| Upstream → Downstream | Patrón | Mecanismo |
|---|---|---|
| Evaluation Design → Pedagogical Evaluation | Customer/Supplier + Published Language | `InstrumentVersionPublished` + `getInstrument(version) → InstrumentSnapshot` (autocontenido). Evaluation guarda **solo** `instrumentVersion`. |
| Evaluation Design → Evaluation Studies | Customer/Supplier + **regla de pinning** | El study fija una versión de instrumento al abrirse, para toda su vida. |
| Evaluation Design → Content Profiling | Published Language del **namespace de ids** (Profiling = **Conformist**) | Design mintea ids + definiciones (ADR-0014); cada adapter mapea sus extracciones a esos ids al escribirse. Nunca strings. |
| Evaluand Registry → Content Profiling | Customer/Supplier | `ContentVersionRegistered` (paquete + brief + generador) + `getContentPackage(contentId)`. |
| Content Profiling → Pedagogical Evaluation | Customer/Supplier + Published Language | `ContentProfiled` + `getProfile(contentId) → ContentProfileSnapshot` (datos por id + `EvidenceProvenance` + versión de adapter). |
| Pedagogical Evaluation → Evaluation Studies | Customer/Supplier (subscriber) | Studies suscribe `QualityJudgmentPublished`, `FindingRaised`, hechos de acuerdo; compone su informe con queries batch (ADR-0006). |
| Pedagogical Evaluation → Evaluation Design (bucle B) | Customer/Supplier (subscriber) | Design suscribe hechos crudos (`DisagreementDetected`, `FindingDisputed`) + queries; el diagnóstico es interno de Design. |
| Evaluand Registry → Evaluation Studies | Customer/Supplier (query) | Studies compone su `EvaluationDataset` **seleccionando** de lo registrado. Pedir más generación es humano y sale del sistema. |
| Orchestration → Evaluation Studies | Subscriber, **cableado por el actor** | El admin abre la campaña por UI referenciando dataset + versión de instrumento; Studies solo observa `ContentEvaluationCompleted`. Sin comandos cruzados. |
| (todos) → Reporting · Identity → (todos) · Orchestration → Golden | sin cambios | Conformist por query ports (ADR-0006) · Open Host Service · subscriber. |

## Reglas de integración

Las cinco originales siguen intactas (async por eventos · queries sync read-only · **sin
comandos cruzados** · published language por upstream · contratos estables
modulith→microservicios). Se agregan **tres**:

1. **Pinning (Studies↔Design).** Un study fija exactamente una versión de instrumento y una
   receta de briefs; la evolución del instrumento jamás muta un study abierto ni re-emite
   resultados publicados. Comparar solo **dentro de una línea**; instrumento nuevo ⇒ línea
   nueva.
2. **Namespace.** Todo requisito de datos y toda capacidad de adapter referencian ids del
   namespace de Design. La oferta sin consumidor queda deliberadamente **fuera de contrato**
   (extras no-canónicos, informales — ADR-0014).
3. **Cadena de provenance.** Todo juicio referencia `{instrumentVersion, adapterVersion,
   assessorId, contentVersion}`; todo finding lleva su cita.

## Queries compuestas (sin dueño de estado — composición ADR-0006)

- **Matching:** demanda (ids de Design) × oferta (capacidades de Profiling) → **cobertura
  esperada** + **demanda insatisfecha**, antes de evaluar nada.
- **Readiness:** encargo (Studies) × claims/instrumentos publicados (Design) × capacidades +
  `ExtractionAccepted` (Profiling) → reporte de huecos **por claim** ("claim sin criteria" ·
  "criterion sin dato en este formato" · "extracción no aceptada"). Es la respuesta operativa a
  "¿faltan instrumentos?" / "¿listo?". **Informa, no bloquea.**

## Arranque en frío

Cadena que precede a todo instrumento: **propósito del encargo → claims → evidence models →
criteria → ids → capacidades.** Señales: un study en estado *Declared* (instrumento pendiente)
= "faltan instrumentos", con el hueco nombrado por claim vía readiness. El análisis de dominio
en frío usa el **canal informal**: extracción exploratoria con nombres provisionales
no-canónicos, **antes** de que exista demanda — sin reabrir el minteo especulativo. La génesis
es demand-driven (claims), pero **se alimenta** de la oferta informal; nada decisional depende
del canal informal.

## ACLs — dos bordes

- **Intake** (borde de Evaluand Registry): API externa → `ContentPackage` + hechos de origen.
  Mecánico, delgado.
- **Extracción** (adapters de Profiling): paquete crudo → `ContentProfile` canónico.
  Interpretativo, uno por `PackageFormat`, testeable por fixtures (ADR-0009).
- Providers LLM (adapter `LLMJudge` en Evaluation): `[futuro]` cercano. Frameworks de
  observabilidad/evals (Langfuse/MLflow/LangSmith): **probable como infraestructura** (tracing,
  annotation queues, export), **nunca como modelo**; colisión de nombres cubierta por ACL de
  código + tabla de equivalencias del `GLOSSARY.md`.

## Published language por contexto

- **Design:** `InstrumentSnapshot` (claims + criteria con condición de pase y modos de falla +
  evidence models + assembly + task bindings) · namespace de ids · eventos.
- **Profiling:** `ContentProfileSnapshot` · capacidades declaradas · eventos.
- **Registry:** DTOs de `ContentPackage`, `GenerationBrief`, `GeneratorVersion` · eventos.
- **Evaluation:** `QualityJudgment` (claims con estatus + perfil por criterion + cobertura) ·
  `Finding` · eventos + hechos de acuerdo.
- **Studies:** `StudyReport` · `StudiesComparison` · eventos.
- **Orchestration:** sin cambios.

## Decisiones de Connect

1. Profiling **Conformist** del namespace de Design (no shared kernel — reabría la gobernanza
   bilateral descartada en ADR-0014).
2. `InstrumentSnapshot` **autocontenido** (el patrón `RubricSnapshot` del slice 1, que probó
   funcionar).
3. **Studies nunca comanda a Orchestration** — el cableado humano lo hace el actor por UI.
4. La oferta sin consumidor **fuera de contrato** — es el medio del análisis de dominio en frío,
   no datos sobrantes. Se formalizaría solo con un trigger de ADR-0014.
</content>
