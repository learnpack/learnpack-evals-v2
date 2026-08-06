# ADR-0018 — Cobertura declarada del assessor automatizado: abstenciones explícitas y el estado `not_assessed`

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation ·
Identity

## Contexto

ADR-0016 (cláusula 3) fijó que cada assessor automatizado declara un instrumento target y
que "la cobertura del target se **valida al registrarlo** (mapeo completo sobre todos los
criteria)". El plan de código lo realiza igual (13-code §3.5: el registry "valida en el
registro que el mapeo cubra todos los criteria del target").

El primer instrumento real (`learnpack-course-qa-v1`, 5 claims / 11 criteria) rompe ese
supuesto: contiene criteria de juicio pedagógico — `cr-module-single-topic`,
`cr-arc-character`, `cr-modules-intro-then-apply`, `cr-objectives-observable-verbs` — que
un assessor código-puro no puede ejecutar, y el MVP no tiene adapter LLM (el mecanismo con
LLM es `[futuro]`). Cumplir la letra de la cláusula 3 deja dos salidas, ambas malas:
bloquear el registro de todo assessor código-puro contra este instrumento, o forzar
ejecutores que fingen juzgar lo que no pueden.

Omitir esos criteria tampoco es salida: 12-define (Pedagogical Evaluation, inv. 1) exige
**cobertura exacta** — "un outcome por cada criterion del `instrumentVersion` — ni falta ni
sobra" — y un assessor que deja criteria sin outcome la rompe, volviendo un bug de omisión
indistinguible de una limitación conocida.

## Decisión

**La cobertura exigida al registro es declarada exhaustiva, no ejecutada exhaustiva; lo no
ejecutable produce un quinto estado de outcome, `not_assessed`, derivado mecánicamente.**

1. **Cobertura declarada.** El paquete del assessor declara dos conjuntos disjuntos: el
   mapeo `criterion_id → ejecutor` y una lista de **abstenciones**
   (`criterion_id → razón corta`, p.ej. "requiere juicio semántico"). La validación del
   registro pasa a ser: *mapeo ∪ abstenciones == criteria del target, sin solapamiento*.
   Se conserva exactamente lo que ADR-0016 quería atrapar — un criterion nuevo en el
   instrumento sigue forzando versión nueva del assessor y una decisión consciente
   (ejecutarlo o abstenerse) — pero la decisión puede ser honesta.
2. **`not_assessed`.** Cada criterion abstenido produce una fila explícita en
   `criterion_outcomes` con outcome `not_assessed`, sin cita (la exigencia de cita queda
   solo para `pass`/`fail`). Semántica: *el dato está y el criterion es juzgable; este
   assessor declaró no poder juzgarlo*. Es una causa distinta de `no_evidence` (el dato
   está ausente del contenido) y de `not_applicable` (sin capacidad del formato o
   condicional excluido): tres causas, tres remedios — mejor generador · mejor extracción
   o formato · mejor assessor.
3. **La derivación sigue siendo mecánica.** La invariante "los desenlaces no-scored se
   derivan mecánicamente, nunca los decide el assessor" se preserva: la abstención se
   declara al **registrar** y es parte de la identidad inmutable de la versión del
   assessor (ADR-0016: cualquier cambio ⇒ versión nueva). En `EvaluateContent`, los
   criteria juzgables que caen en la lista de abstenciones pasan a `not_assessed` por
   derivación, sin intervención del assessor en runtime.
4. **Sufficiency y denominador.** Bajo la sufficiency conjuntiva (13-code §7.1),
   `not_assessed` cae en "cualquier otro caso": el claim queda `insufficient` — ni
   soportado ni refutado; la regla no cambia. En el denominador de ADR-0011,
   `not_assessed` queda **dentro** (como `no_evidence`); solo `not_applicable` queda
   fuera. La `evidence_basis` por claim pasa a contar
   `{pass, fail, no_evidence, not_applicable, not_assessed}` y la cobertura del judgment
   pasa de terna a cuaterna (evaluados / no aplican / sin evidencia / sin assessor capaz):
   cada "insuficiente" queda calificado con su causa.
5. **La cobertura exacta se conserva por construcción**: un outcome por criterion del
   snapshot, ahora sobre cinco estados. Deltas de realización sobre 13-code §3.5 (snapshot
   congelado que este ADR enmienda): la CHECK de `criterion_outcomes` suma
   `'not_assessed'`; la validación del registry valida la unión disjunta; los conteos de
   `evidence_basis` y el jsonb `coverage` del judgment suman la causa nueva.

## Relación con ADR-0016

**No lo supersede.** ADR-0016 decide la taxonomía `human | automated`, el assessor como
artefacto modular versionado con instrumento target, y la invalidación por identidad —
todo eso sigue vigente. Esta ADR refina su cláusula 3: la validación del registro deja de
exigir mapeo ejecutable completo y pasa a exigir **declaración completa** (mapeo +
abstenciones). El propósito de la cláusula — que ningún criterion del target quede sin una
decisión consciente del autor del assessor — se cumple igual.

## Consecuencias

- (+) El sistema dice la verdad: los claims de juicio quedan `insufficient` con causa
  visible ("sin assessor capaz"), no falsamente juzgados ni silenciosamente omitidos. Los
  `not_assessed` acumulados son el **backlog visible** del assessor con LLM (o humano):
  la demanda que justifica priorizarlo, medible por instrumento y por criterion.
- (+) El registro sigue atrapando criteria olvidados: agregar un criterion al instrumento
  sin tocar el assessor sigue fallando la validación de unión disjunta.
- (+) Ningún cambio en la sufficiency ni en la regla del denominador: solo se añade una
  causa distinguible.
- (−) Un estado más en el enum, en queries y en la UI futura de judgments/reports.
- (−) Los reports deben distinguir las causas de `insufficient` para que el estado no se
  lea como ruido; `evidence_basis` lo hace posible, los studies deben hacerlo (la regla
  de caveats de 12-define ya lo exige).
- (−) El GLOSSARY reescribe su "tri-estado" (Criterion, CriterionScore, QualityJudgment,
  tabla de equivalencias): el desenlace pasa a
  `scored (pass/fail) | not_applicable | no_evidence | not_assessed`.

## Alternativas consideradas

- **Ejecutores-stub que "cubren" todo devolviendo abstención** → rechazada: cumple la
  letra de ADR-0016 con pura ceremonia (un stub por criterion de juicio), y el quinto
  estado hace falta igual para que el outcome diga la verdad.
- **Mapear la abstención a `no_evidence`** → rechazada: miente — confunde "dato ausente"
  con "juez ausente" y rompe la distinción causa/consecuencia de 12-define (Evaluation
  Design inv. 3); los studies no podrían separar qué se arregla con mejor generación y
  qué con mejor assessor.
- **Omitir la fila (sin outcome para lo abstenido)** → rechazada: ausencia-como-dato;
  rompe la cobertura exacta por construcción (PE inv. 1) y un bug de omisión se vuelve
  indistinguible de una abstención deliberada.
- **Relajar la validación sin abstención explícita** (aceptar mapeo parcial) → rechazada:
  un criterion nuevo en el target pasaría inadvertido — exactamente el churn silencioso
  que la cláusula 3 de ADR-0016 quería impedir.

## Referencias

ADR-0016 §3 (la cláusula refinada) · ADR-0011 (regla del denominador: `not_applicable`
fuera, el resto dentro) · ADR-0010 (desenlace + cita) · ADR-0015 (la capa 2 humana
verifica la consistencia norma/realización; los `not_assessed` son también su cola de
trabajo natural) · 12-define: Pedagogical Evaluation inv. 1–2, Evaluation Design inv. 3,
Content Profiling inv. 3 · 13-code §3.5 y §7.1 (la realización que este ADR enmienda) ·
el instrumento `learnpack-course-qa-v1` (los cuatro criteria de juicio que originaron la
decisión).
