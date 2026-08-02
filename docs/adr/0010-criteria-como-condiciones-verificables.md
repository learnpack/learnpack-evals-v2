# ADR-0010 — Los criteria son condiciones verificables, no escalas de apreciación

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Rubric Authoring / Pedagogical
Evaluation

## Contexto

`Rubric v1` define 5 criteria, uno por dimensión pedagógica, cada uno con escala 1–5 y anchors
genéricos (`docs/seed/rubric-v1.json`, `07-define.md`). Cada criterion colapsa varias qualities en
una pregunta de apreciación: *"¿qué tan buena es la calidad de los objetivos?"*.

Al abrir el motor a fuentes automáticas aparecen dos problemas con esa forma:

1. **Un verificador determinístico no produce un 3,7.** Produce un booleano o una medición con
   unidades. Mapear eso a 1–5 exige umbrales arbitrarios, y toda la subjetividad se concentra en
   un `ScoringPolicy` opaco.
2. **Una escala de apreciación no es auditable.** "Los objetivos son un 3" no se puede rastrear,
   discutir ni reproducir. "Menos de 3 objetivos declarados" sí.

Además, dos sistemas maduros e independientes convergieron en lo contrario de lo que hicimos:
`k12-teacher-skills` usa criteria binarios (pass/fail) con una condición explícita —*"At least 3
misconceptions or anticipated challenges named"*, *"All three components in every entry"*— y
recupera matiz teniendo **muchos**; Quality Matters juzga **Met / Not Met** por standard.

## Decisión

**La unidad de juicio es una condición verificable sobre el contenido, no un punto en una escala.**

1. **Todo `EvaluationCriterion` define una condición de pase explícita y puntuable**
   (*what pass requires*): una afirmación que sobre un contenido dado es verdadera o falsa. Es un
   campo del criterion, distinto de su enunciado y de su guía.
2. **El criterion enumera además sus modos de falla**, con ejemplo del mal caso cuando ayude
   (*"Fail = cita solo por código, paráfrasis o variación de redacción"*). Hace consistente al
   juez, sea humano o LLM.
3. **El desenlace de un criterion es tri-estado**, no un número: `scored` (evaluado) ·
   `not_applicable` (el criterion no corresponde a este contenido) · `no_evidence` (corresponde y
   el contenido no lo tiene — ver ADR-0009). Un criterion `scored` resuelve **pass / fail**.
4. **El matiz se recupera con granularidad, no con escala:** una cualidad compleja se
   operacionaliza en varios criteria chicos y verificables, no en uno con cinco niveles.
5. **El criterion declara los datos que necesita** del `ContentProfile`. Si no están disponibles,
   el desenlace es `not_applicable` o `no_evidence` según el criterion — nunca un score inventado
   ni un error.
6. **Un criterion cuya condición no se puede enunciar de forma verificable es señal de que está
   mal descompuesto**, no de que necesite una escala.

## Consecuencias

- (+) **Habilita el determinismo.** Un check estructural sobre el `ContentProfile` ("al menos 3
  objetivos declarados", "cada evaluación referencia un objetivo") se computa sin LLM. Es el
  puente entre el `ContentProfile` y la evaluación determinística que buscábamos.
- (+) **Auditable y discutible.** El colaborador puede debatir una condición; no puede debatir un
  3,7.
- (+) **Mejora el acuerdo entre evaluadores**, humanos o automáticos: una condición binaria tiene
  mucho menos ruido que una escala ordinal.
- (+) Encaja con ADR-0011: pass rates por criterion es lo que se reporta.
- (−) **Hacen falta muchos más criteria.** k12 usa 35 para *un plan de lección*; hoy tenemos 5
  para *un curso entero*. Escribirlos es trabajo real — y es precisamente el trabajo del
  colaborador.
- (−) **`Rubric v1` no cumple esta forma.** Sus 5 criteria son escalas de apreciación. Hay que
  decidir explícitamente si se migra o se marca legacy (ver abajo). **Esta ADR no lo decide.**
- (−) Se pierde la granularidad aparente del 1–5. Es aparente: esa granularidad nunca estuvo
  fundamentada en nada verificable.

## Alcance y migración de `Rubric v1`

Esta decisión rige **el modelo de criterion y toda rubric nueva**. No migra por sí sola la rubric
existente ni el flujo humano ya construido (que asume `score ∈ [1,5]`).

Dato relevante para esa decisión: **hoy no hay evaluaciones cargadas** —la recolección humana se
despriorizó—, así que el coste de migrar v1 es mínimo *ahora* y crece apenas el colaborador
empiece a iterar sobre ella. Queda como decisión abierta y consciente, registrada en
`notes/estado-exploracion-slice2.md`.

## Alternativas consideradas

- **Mantener 1–5 en todos los criteria** → rechazada: incompatible con fuentes determinísticas sin
  umbrales arbitrarios, y no auditable.
- **Escala 1–5 para criteria de juicio y binario para los computables** → rechazada: dos monedas
  distintas en la misma rubric, imposibles de componer o comparar; además empuja a clasificar
  criteria por su implementación en vez de por lo que afirman.
- **Rúbrica holística (un score global por dimensión)** → rechazada: es lo contrario de lo que la
  evidencia recomienda; las rúbricas analíticas superan a las holísticas justamente en
  trazabilidad.
- **Escala con anchors por criterion** (en vez de genéricos) → mejora el problema pero no lo
  resuelve: sigue sin ser verificable y sigue sin admitir salida determinística.
</content>
