# ADR-0015 — Referencia humana en dos capas: panel por quality + verificación muestreada

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation ·
Evaluation Studies · Golden Dataset · Calibration `[futuro]`

## Contexto

La evaluación humana experta es cara en tiempo y dinero; un equipo chico no puede correr
campañas de SMEs cada vez que cambia un instrumento. A la vez, el juicio humano es la fuente
para responder la pregunta de calibración central: *¿cuánto coinciden los assessors no-humanos
con los expertos?*

La revisión pre-cierre de Define encontró además un hueco estructural: la ejecución de
instrumentos exige `ContentProfile` (DP17/DP18 — coordenadas con `adapterVersion`, derivación
mecánica del tri-estado), con lo cual **un humano no podía evaluar contenido sin adapter
aceptado** — bloqueando el camino "evalúo con humanos mientras construyo el adapter". El hueco
existía porque el modelo fusionaba **dos roles humanos distintos**.

La práctica de industria está asentada: alinear jueces contra un **set etiquetado por humanos
una sola vez** y reusarlo en cada iteración del juez (kappa ≥ 0.60 como umbral típico, ~50
ítems etiquetados antes de automatizar); **verificación humana muestreada al 5–10%** con colas
priorizadas por bajo acuerdo; re-muestreo periódico contra deriva. EvalGen (UIST 2024) aporta el
*catch-22*: es calificando outputs como los humanos descubren sus propios criterios — la
calibración humana alimenta el diseño, no solo lo controla.

## Decisión

**La participación humana tiene dos modos, con reglas distintas; la referencia se compra una vez
y se reusa; la verificación continua se muestrea.**

1. **Modo panel de referencia (capa 1).** SMEs juzgan las **qualities directamente**, leyendo el
   contenido — **fuera de la ejecución de instrumentos, sin profile**. La elicitación es
   holística por quality/dimensión (escala ordinal): forma apropiada para juicio directo de
   constructo (el patrón Achieve OER). **No está sujeta a ADR-0010**, cuyo alcance son los
   criteria del argumento evidencial — este es otro artefacto con otras reglas.
2. **Modo assessor/verificador (capa 2).** Dentro de la ejecución de instrumentos, el humano
   trabaja **sobre el profile**, verificando outcomes **citados** ("el sistema dice que no hay
   objetivos; acá está la extracción — ¿correcto?"). El prerequisito de profile (DP17/DP18)
   **se mantiene intacto**: el hueco no se tapa, se disuelve — la necesidad que parecía
   bloqueada la sirve el modo referencia.
3. **`Rubric v1` NO se migra: se estabiliza como el instrumento de referencia de la capa 1**
   (criterion↔dimensión 1:1, escala 1–5). Su estabilidad es una **feature**: una referencia que
   cambia no es referencia. La deuda "migrar v1 a la forma ADR-0010" se cancela; la reemplaza
   una revisión ligera (anchors, definiciones) antes de la primera campaña de referencia.
4. **La comparación instrumento↔referencia no suma nada: coeficientes de validez por claim.**
   Cada claim se correlaciona con el score humano de **su** quality a través de los contenidos
   del set — diagnóstico por claim ("cuáles rastrean el juicio experto"), jamás sumas a
   dimensión (el argumento de ADR-0011 aplicado a calibración). Las métricas de acuerdo son
   **artefactos de calibración** (como la dispersión de ADR-0006), no juicios publicados.
5. **El techo se mide primero:** el acuerdo juez-humano se reporta siempre junto al acuerdo
   humano-humano (inter-rater, ADR-0006), que es su cota superior.
6. **Verificación muestreada** (capa 2): % configurable, colas priorizadas por desacuerdo,
   impugnaciones y criteria nuevos; re-muestreo periódico. ADR-0009/0010 abarataron esto por
   construcción: **verificar un check citado cuesta minutos; producir un juicio holístico,
   horas.**
7. **Refresh incremental de la referencia** cuando la distribución de contenido cambia (los
   briefs pareados de ADR — DP12 — ayudan a extenderla de forma comparable). Sin re-campañas
   completas.

## Consecuencias

- (+) Resuelve el hueco #1 de la revisión **sin maquinaria nueva**: el modo referencia usa lo ya
  construido (Rubric v1 + campañas + quórum + `GoldenDataset`).
- (+) Una campaña cara, reusada contra **todas** las versiones de instrumento (ancladas en las
  qualities — la columna estable del lenguaje); validación continua barata y priorizable.
- (+) Diagnóstico accionable: validez por claim, no correlaciones por dimensión.
- (+) El catch-22 de EvalGen queda capturado: la verificación humana alimenta el bucle B.
- (−) La referencia holística es ruidosa: el techo lo pone el inter-rater humano — hay que
  medirlo y reportarlo, no asumirlo.
- (−) Deriva de constructo a vigilar: los claims referencian `qualityId` con definición; los
  cambios de lectura de una quality invalidan comparaciones silenciosamente si no se revisan.
- (−) `GoldenDataset` gana un rol adicional (referencia de calibración de instrumentos, además
  de ground truth para calibración de assessors `[futuro]`); su canvas se ajusta al promover.

## Alternativas consideradas

- **Humanos ejecutando instrumentos nuevos sin profile** (con sus propias citas) → rechazada:
  rompería la derivación mecánica de DP18 y duplicaría el rol del extractor dentro del acto de
  juicio; la necesidad real la cubre el modo referencia, con maquinaria existente.
- **Migrar Rubric v1 a checks** (el plan previo, registrado en STATUS) → reemplazada: destruiría
  la referencia estable y su forma holística — que es la apropiada para elicitación directa de
  constructo.
- **Campañas SME por versión de instrumento** → inviable: es el problema a resolver, no una
  opción.
- **Comparar sumando scores a quality/dimensión** (la idea original) → rechazada: la suma
  destruye el diagnóstico — no dice *qué* claim diverge (mismo argumento que ADR-0011).

## Referencias

Calibración de jueces con anotaciones humanas: https://galileo.ai/blog/calibrate-llm-judge-human-annotations ·
https://www.evidentlyai.com/blog/how-to-align-llm-judge-with-human-labels ·
https://www.langchain.com/resources/llm-as-a-judge · HITL y colas de anotación:
https://www.braintrust.dev/articles/best-human-in-the-loop-llm-evaluation-platforms-2026 ·
EvalGen, "Who Validates the Validators?" (UIST 2024): https://arxiv.org/abs/2404.12272 ·
Razonamiento completo en `notes/` (exploración slice 2).
</content>
