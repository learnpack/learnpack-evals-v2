> ⚠️ **SNAPSHOT HISTÓRICO (jul-2026)** — diseño que produjo el slice 1 (MVP humano). El diseño
> vigente es la serie **`09-align-discover-qa.md` … `12-define-qa.md`** (QA interno). **No usar
> este doc como fuente para código nuevo.**

# 01 — Align

> Paso 1 del DDD Starter Modelling Process (ddd-crew). Estado: **cerrado (v0, living)**.
> Fases del proceso: Understand → **Align** → Discover → Decompose → Strategize →
> Connect → Organise → Define → Code. Iterativo: se repite Discover→Organise antes de
> Define; Define y Code pueden ir en paralelo.

## Visión de producto

Un sistema para **evaluar la calidad pedagógica de contenido educativo generado (total o
parcialmente) por IA generativa**. Evalúa contenidos de distinto formato y procedencia,
mediante distintas **fuentes de evaluación** (SME humano, LLM-as-judge, verificadores
determinísticos, híbridos) y bajo distintos **criterios/enfoques pedagógicos**, de forma
modular e intercambiable. Produce juicios de calidad trazables y comparables
(score + evidencia/comentario), y permite **calibrar y validar** las evaluaciones
automáticas contra una referencia humana.

## Qué es el core (y qué NO)

- **Core = evaluación pedagógica.** El significado de "calidad pedagógica", los criterios/
  rúbricas, la producción de un juicio, y la representación de múltiples **fuentes** y
  **enfoques**. Ahí vive el diferenciador.
- **La calibración NO es el core.** Es un subdominio de *soporte* que alimenta al core. La
  evaluación humana del MVP es simplemente *una fuente (HumanExpert) ejerciendo el core*,
  envuelta en orquestación (asignar cursos, ver pendientes).

## Framing estratégico (insumo del paso 4, Strategize)

- **Core** → *Pedagogical Evaluation*: criteria/rubrics, producción de juicios, taxonomía
  de fuentes, grounding en frameworks, separación medición/score.
- **Supporting** → Evaluation Orchestration (campaigns, assignments, pendientes) ·
  Golden Dataset management · Calibration.
- **Generic** → Identity/users · Content registry & metadata · Notifications ·
  Projections/reporting · Localization (i18n).

## Dos horizontes (no confundir en la implementación)

1. **Modelo objetivo** — app modular, fuentes/criterios intercambiables, modular monolith
   + domain events (evolucionable a microservicios). Se **diseña completo** aunque no se
   implemente ya.
2. **Slice del MVP** — herramienta de evaluación humana para construir el golden dataset,
   la más ligera posible (Google Sheets como store si acelera), sin deploys pagos, lista en
   horas. Es una **rebanada vertical fina** consistente con el modelo objetivo, sin ceremonia
   de clean architecture completa. Los docs preservan el norte; el código crece hacia ahí.

> ⚠️ Riesgo a evitar: intentar construir el modulith completo en horas. El MVP es
> deliberadamente simple; la calidad la garantizan los boundaries documentados, no la
> ceremonia prematura.

## Alcance del MVP (features priorizadas)

Prioridad absoluta: **que las personas puedan evaluar cursos y que esa data quede guardada.**
Las proyecciones/reportes pueden venir después.

- Crear un golden dataset de ~50 cursos e-learning (registro liviano: `GeneratingSystem`,
  id externo, url consumible, metadata a definir, id propio). Sin almacenar el contenido
  completo.
- Registrar evaluadores y asignarles cursos (`Assignment`).
- Definir la lista de preguntas (= `LearnPack Pedagogical Rubric v1`, 5 criteria).
- Flujo del evaluador (3 pasos): 1) ver metadata · 2) acceder al contenido (url; iframe si
  es viable) · 3) responder el formulario (5 criteria, score 1–5 obligatorio + comentario
  opcional, con hints de qué es 1 y qué es 5).
- Persistir respuestas (qué evaluador, qué curso, qué scores).
- Vistas de admin: quién evaluó qué / pendientes; scores por curso (individual y promedios).

## Decisiones y restricciones registradas

- **Idioma:** ubiquitous language y código en **inglés**; docs y diálogo en español.
- **UI i18n:** objetivo EN/ES; **MVP English-only**.
- **LearnPack:** contenido accesible por url tipo
  `https://introduction-to-generative-ai.learn-pack.com/`; metadata a mano por ahora.
  Riesgo a verificar en el paso Code: `X-Frame-Options`/`CSP frame-ancestors` puede
  bloquear el iframe → fallback "abrir en pestaña nueva".
- **Evaluadores:** SMEs internos y externos, expertise variado; identificación simple para
  el MVP (sin auth robusta).
- **Costos:** sin deploys pagos en la primera versión.

## Modelado conceptual acordado en Align

Ver `../GLOSSARY.md`. Puntos clave que gobiernan el diseño:

1. **Framework como grounding, no como contenedor.** `Criterion` cita frameworks (N:M);
   los frameworks/dimensiones/qualities son *reference data versionada*, no están
   hardcodeados (el equipo puede cambiarlos).
2. **Ejes ortogonales e intercambiables:** `Content` (qué) · `Criterion`/`Rubric` (qué se
   mide) · `EvaluationSource` (cómo se produce). Con una relación de compatibilidad
   `eligible_sources` entre `Criterion` y `Source`.
3. **`EvaluationSource` es un port con 4 adapters:** HumanExpert, LLMJudge,
   DeterministicVerifier, HybridVerifier ("Hybrid Norm").
4. **Medición ≠ juicio:** las fuentes determinísticas/híbridas producen `ComputedMetric`
   (señal cruda) que una `ScoringPolicy` mapea a `CriterionScore`; humano/LLM puntúan
   directo. Ver `research/deterministic-evaluation-landscape.md`.
5. **El `criterion` es la clave de join de la calibración:** la misma rubric puntuada por
   distintas fuentes permite comparar automático vs. referencia humana por criterion.

## Business model (canvas liviano)

- **Propuesta de valor:** juicios de calidad pedagógica trazables, comparables y
  auditables sobre contenido generado por IA, con fuentes intercambiables (humano/
  automático) y calibrables contra referencia humana.
- **Usuarios:** admin (curador/calibrador) · evaluadores SME · (futuro) consumidores de
  reportes de calidad; sistemas generadores como origen del contenido (LearnPack).
- **Actividad clave inmediata:** construir el golden dataset humano (fuente de verdad para
  calibrar).
- **Restricciones:** tiempo (horas para el MVP), costo (sin deploys pagos).

## Estado y próximo paso

- Align: **cerrado**.
- Siguiente: **02 — Discover** (Big-Picture EventStorming del dominio de evaluación, con
  las 4 fuentes como ramas paralelas y `LLMJudge`/`Calibration` incluidos aunque no entren
  al MVP). El slice del MVP saldrá como recorte de esa línea de tiempo.
