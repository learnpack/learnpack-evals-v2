# Research note — Insumos del rediseño QA interno (slice 2)

> Insumos externos fechados (jul–ago 2026) que fundamentan la serie 09–12 y los ADRs 0009–0015.
> Congelado; afirmaciones parafraseadas, ver fuentes. Complementa
> `deterministic-evaluation-landscape.md` (jul-2026).

## 1. Cómo evalúan calidad pedagógica los equipos humanos profesionales

Sistemas estudiados: EdReports (currículos K-12), Quality Matters (cursos online), EQuIP
(lecciones/unidades), adopción distrital, QA editorial, norming/moderación.

- **Proceso consistente:** instrumento versionado → certificar/entrenar revisores (EdReports:
  25 h antes de tocar material) → **norming** con anchors (un ejemplar alto y uno bajo con modos
  de falla) → recolección **independiente** de evidencia → consenso argumentado (no promediado)
  → escalamiento (dos revisores → chair → tercer rater) → informe con evidencia → respuesta del
  evaluado → re-revisión del delta → retroalimentación al instrumento.
- **El instrumento son dos documentos:** Review Criteria + **Evidence Guide** (cómo recolectar
  evidencia, por indicador) — la separación extracción/juicio existe en el mundo humano.
- **El desacuerdo es diagnóstico:** sus causas raíz (criterion ambiguo, evidencia insuficiente,
  entrenamiento, conocimiento que cambió) piden correcciones distintas — alta discrepancia
  señala un criterion mal escrito.
- **Versionado:** EdReports v2.0 no re-emite reportes viejos ("no actualiza retroactivamente") —
  origen de nuestra regla de pinning.
- **Negocio:** la credibilidad de EdReports = independencia estructural (no cobra a evaluados);
  el valor del servicio no es el score sino **el cambio que produce** (40+ editoriales ajustaron
  productos). En QA interno la independencia se reemplaza por **trazabilidad a evidencia**.
- Composición: **gateways secuenciales** (EdReports) y **capas de QA** (editorial); Quality
  Matters agrega **gates obligatorios** (essentials que deben cumplirse todos) — la media simple
  es la agregación más débil.

Fuentes: edreports.org/process · qualitymatters.org/why-quality-matters/process ·
achieve.org (EQuIP) · scu.edu (norming) · pubmed 12147915 (third-rater adjudication).

## 2. Diseño de instrumentos: ECD y ECBD

- **Evidence-Centered Design** (Mislevy): evaluación como **argumento evidencial** —
  claim ← acumulación ← observables ← identificación de evidencia ← work product ← tarea; con
  warrants (Toulmin) y **explicaciones alternativas**. El evidence model separa identificación
  (producto → observables) de acumulación (observables → conclusión).
- **ECBD** (ACL 2024): ECD aplicado a evaluar sistemas de IA (benchmarks NLP); cinco módulos
  (capability, content, adaptation, assembly, evidence); diagnóstico: las decisiones de diseño
  de una evaluación "se apoyan en supuestos tácitos y no testeados".
- La aplicación **ECD → calidad pedagógica de contenido generado por IA** no existe publicada:
  este sistema ocupa esa intersección (el examinado es el generador; cada contenido, un work
  product). Adoptado como **ECD-lite** (ADR-0013): 4 piezas, sin maquinaria psicométrica.

Fuentes: ECBD — aclanthology.org/2024.acl-long.861 (arXiv 2406.08723) · Mislevy (CRESST/WestEd,
Implications of ECD) · e-ECD (Frontiers 2019).

## 3. Tooling de evals: terminología y calibración

- **Terminología:** *dataset*, *score*, *LLM-as-judge*, *trace*, *golden dataset*, *annotation
  queue* son términos genuinamente universales. **No hay estándar** para "el que juzga":
  scorer (Braintrust/MLflow) · evaluator (LangSmith/Azure) · metric (DeepEval/Ragas) · grader
  (OpenAI) · assertion (promptfoo) — y todos fusionan el *qué* con el *quién* (nuestra
  separación Criterion × Assessor no se cede). *Experiment* es ambiguo: unidad en
  LangSmith/Braintrust/Phoenix, **contenedor** en MLflow. → Tabla de equivalencias en
  `../../GLOSSARY.md`.
- **Calibración de jueces (judge alignment):** etiquetar una vez con humanos (~50 ítems antes de
  automatizar), iterar el juez contra ese set (kappa ≥ 0.60 como umbral típico); verificación
  humana muestreada al 5–10% con colas priorizadas por bajo acuerdo; re-muestreo periódico
  contra deriva. → base de ADR-0015.
- **EvalGen / "Who Validates the Validators?"** (UIST 2024): el *catch-22* — es calificando
  outputs como los humanos descubren sus propios criterios. La verificación humana alimenta el
  diseño (nuestro bucle B), no solo lo controla.

Fuentes: langfuse.com/docs/evaluation/core-concepts · galileo.ai (calibrate LLM judge) ·
evidentlyai.com (align judge with human labels) · langchain.com/resources/llm-as-a-judge ·
braintrust.dev (HITL platforms) · arxiv 2404.12272 (EvalGen) · deepeval.com · qaskills.sh
(OpenAI evals vs promptfoo vs Ragas).
</content>
