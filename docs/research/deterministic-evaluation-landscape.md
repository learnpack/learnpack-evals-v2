# Research note — Panorama de evaluación determinística / híbrida de calidad pedagógica

> Insumo de diseño recopilado en Align (jul-2026) para enriquecer el modelado de
> `EvaluationSource`, `ComputedMetric` y `eligible_sources`. No es exhaustivo; es una base
> para Discover/Define. Todas las afirmaciones parafraseadas; ver fuentes.

## Tesis central

"Determinístico vs. rúbrica" **no es una dicotomía**: es un espectro de verificadores que
se **combinan** (la "Hybrid Norm"): checks programáticos para las verdades objetivas ("qué"),
rúbricas vía juez LLM para la calidad matizada ("cómo"), y supervisión humana para
gobernanza y calibración.

## Familias de evaluación determinística (o det. + LLM)

### 1. Legibilidad (readability) — totalmente determinística
Fórmulas computables: Flesch-Kincaid Grade Level, Gunning Fog, SMOG, ARI, Dale-Chall.
Estiman el grado escolar/años de educación para comprender un texto. Baratas y
reproducibles; correlación media con nivel percibido por humanos → señal útil, no suficiente.
Aplicable a: "legibilidad adecuada al público objetivo".

### 2. Cohesión y coherencia — determinística sobre features lingüísticos
Herramientas tipo Coh-Metrix / TAACO: decenas de índices (cohesión referencial, conectores,
solapamiento léxico). Diseñadas porque las fórmulas de legibilidad dependen demasiado de
rasgos superficiales; los índices se validan contra juicios expertos de coherencia.
Aplicable a: "secuenciación coherente", "cohesión del material".

### 3. Nivel cognitivo (Bloom / SOLO) — clasificación ML, hoy también LLM
Clasificar objetivos y preguntas por nivel de Bloom es tarea madura (clasificadores
entrenados sobre decenas de miles de objetivos); los LLMs habilitan zero/few-shot.
Aplicable a: "¿los objetivos cubren niveles cognitivos altos o solo recordar?".

### 4. Alineación (curricular y constructiva) — embeddings / matching semántico
Similitud semántica objetivo↔contenido↔evaluación con Sentence-BERT / DeBERTa / RoBERTa
(alineación de ítems a estándares con F1 alto). Operacionaliza el triángulo de Biggs
(constructive alignment: objetivos ↔ actividades ↔ evaluación) y la detección de
desalineación/defectos de ítems.
→ **Encaje directo con `pgvector`.**
Aplicable a: "alineación constructiva", "cobertura de objetivos".

### 5. Presencia/estructura y progresión — chequeos de reglas
Verificaciones tipo "blueprint": ¿hay objetivos explícitos, ejemplos, worked examples,
actividades, evaluación, feedback? ¿el orden respeta prerrequisitos / learning progressions?
Mapean casi 1:1 a Merrill (First Principles) y Learning Progressions.
La **metadata del curso** (objetivos, público, prerrequisitos) es la *referencia* de estos
checks.

## La "Hybrid Norm" (patrón arquitectónico clave)

- Verificadores **programáticos**: deterministas, auditables, **nunca alucinan**, con modos
  de falla enumerables — pero frágiles.
- Jueces **LLM**: flexibles pero opacos; heredan sesgos del modelo.
- Patrones de fusión observados: regla → señal binaria o score base acotado que luego se
  **fusiona** con el juez LLM; en código, LLM evalúa la lógica y un compilador
  determinístico verifica la sintaxis, y se **suman** los puntajes.
- **Rúbricas analíticas** (criterio por criterio) > holísticas (score único y opaco) →
  coincide con cómo modelamos `Rubric`.

## Implicaciones de modelado (llevadas al modelo)

1. `EvaluationSource` = taxonomía de 4 adapters (HumanExpert, LLMJudge,
   DeterministicVerifier, HybridVerifier) detrás de un port.
2. Separar *qué se mide* (`Criterion`, grounded) de *cómo se produce* (`EvaluationSource`).
3. Relación `eligible_sources`: algunos criteria son computables, otros requieren juicio.
4. Introducir `ComputedMetric` (medición cruda) distinto de `CriterionScore` (juicio);
   `ScoringPolicy` mapea métrica→score, a menudo contra un umbral/referencia de la metadata.
5. Regalo para la calibración: los determinísticos se pueden correr sobre los 50 cursos ya
   y correlacionar contra el golden humano por dimensión. Caveat: determinístico ≠ válido
   (las fórmulas tienen límites conocidos) → por eso existe el golden dataset.

## Fuentes (selección)

- COGENT — Curriculum-oriented framework, tríada readability/comprehensibility/curriculum
  alignment (arXiv 2506.09367).
- Coh-Metrix / TAACO — cohesión y coherencia automáticas.
- Readability formulas — Flesch-Kincaid, Gunning Fog, SMOG, ARI, Dale-Chall.
- Bloom auto-classification — EDM 2022 (Monash, 21k objetivos); BEA 2025 (Kolagar et al.);
  Almatrafi & Johri 2025 (GenAI para categorización de outcomes).
- Item↔standard alignment — DeBERTa/RoBERTa/Sentence-BERT (arXiv 2510.05129).
- Constructive alignment (Biggs) — triángulo objetivos/actividades/evaluación; alineación
  de MCQ a objetivos (BMC Med Educ 2025; arXiv 2506.23815).
- Hybrid Norm / RLVR — verificadores programáticos vs. aprendidos vs. híbridos
  (rlvrbook.com cap.4); RaR / RLCF; Autorubric (arXiv 2603.00077); KnowU-Bench hybrid
  (arXiv 2604.08455); "Rubric is all you need" (ICER 2025).
