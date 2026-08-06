# ADR-0019 — Cobertura del assessor por linaje de criteria: ratificación por versión sin cambio de identidad

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation ·
Identity · Evaluation Design

## Contexto

ADR-0016 (cláusula 3) ata cada assessor automatizado a **una versión** de instrumento
(`instrument_version_id`); ADR-0018 refinó qué exige esa atadura (declaración completa:
mapeo ∪ abstenciones == criteria del target). La consecuencia que ADR-0016 ya anotaba —
"un criterion nuevo en el target exige versión nueva del assessor" — resultó, en la
realización, bastante más ancha: **cualquier versión nueva del instrumento** fuerza una
versión nueva de cada assessor que lo targetea, aunque el cambio no toque ningún criterion
que ese assessor ejecuta (o toque solo criteria de los que se abstiene) y su código quede
byte-idéntico.

Eso contradice el argumento del propio ADR-0016, que rechazó la librería de checks
compartida por **churn de identidad espurio** ("cualquier cambio en cualquier función
cambiaba la identidad de todos los jueces a la vez — invalidación espuria"). El target por
versión reproduce ese churn a granularidad de instrumento: la identidad del assessor muere
— y con ella su calibración, que "no transfiere" por regla — cuando nada de lo que el
assessor es o hace cambió. La calibración de un artefacto idéntico juzgando criteria
idénticos **sí** transfiere; invalidarla es incorrecto, no solo laborioso.

El costo cae justo donde más se itera: la fase de calibración de un instrumento
(`learnpack-course-qa-v1` es el caso presente) produce versiones en sucesión rápida —
cada ajuste de redacción o umbral es una versión nueva, porque publicado es inmutable — y
cada una arrastra un bump ceremonial de todos sus assessors.

El sustrato para algo mejor ya existe por diseño: `claimId`/`criterionId` son **estables
entre versiones** (linaje, 12-define §Evaluation Design inv. 1) — precisamente para que
otras piezas puedan referirse a un criterion a través de las versiones.

## Decisión

**La cobertura del assessor automatizado se declara sobre el linaje de criteria de su
instrumento; su validez para cada versión concreta se establece por un acto explícito de
ratificación, que no cambia la identidad del assessor.**

1. **El assessor se debe a un instrumento (linaje), no a una versión.** Su declaración es
   `instrument_id` + cobertura por `criterion_id`: mapeo `criterion_id → ejecutor` ∪
   abstenciones, conjuntos disjuntos (ADR-0018, intacto) — keyada por los ids estables del
   linaje.
2. **Ratificación por versión.** Un assessor es elegible para evaluar contra una versión
   del instrumento solo si esa versión está **ratificada** para él. El registro inicial
   ratifica la primera versión con la validación de ADR-0018 tal cual: cobertura
   (restringida a los criteria de esa versión) == criteria de la versión, sin solapamiento.
3. **Compatibilidad computada; decisión humana solo sobre el delta.** Ratificar una
   versión nueva computa mecánicamente el diff sobre el linaje:
   - Criterion cuyo **texto normativo realizado por el ejecutor** (`pass_condition` +
     `required_data`, comparación literal) está sin cambios → su entrada de cobertura
     (ejecutor o abstención) se conserva sin intervención.
   - Criterion **nuevo o cambiado** → exige decisión explícita del autor antes de que la
     ratificación proceda: abstenerse · confirmar que el ejecutor existente realiza el
     texto nuevo (la consistencia norma/realización la verifica la capa 2 humana,
     ADR-0016 cláusula 6) · o cambiar el ejecutor — lo que es un cambio del artefacto y
     por tanto **versión nueva del assessor** (cláusula 2, intacta).
   - Campos del criterion realizados por la **derivación mecánica**, no por el ejecutor
     (`on_missing_evidence`, `condition`), y los bindings del instrumento, no invalidan
     cobertura.
4. **La identidad no se toca.** La versión del assessor sigue siendo la identidad de su
   artefacto de software (código, mapeo, config): cualquier cambio del artefacto ⇒ versión
   nueva ⇒ otra identidad (ADR-0016 cláusula 2). Ratificar versiones del instrumento no es
   un cambio del artefacto; la calibración transfiere sobre criteria idénticos y se
   invalida solo donde algo cambió de verdad.
5. **La forcing function se conserva.** Ningún criterion llega a una evaluación sin
   decisión consciente del autor del assessor: la versión no ratificada no es evaluable
   por ese assessor (`EvaluateContent` exige assessor con la versión pedida ratificada), y
   el delta de cada ratificación exige decisión explícita — el propósito de ADR-0016 §3 y
   de ADR-0018, ahora a costo proporcional al cambio real.
6. **Deltas de realización sobre 13-code §3.5** (snapshot congelado que este ADR
   enmienda): el `source_config` del assessor declara `instrument_id` + cobertura por
   `criterion_id` (no un `instrument_version_id`); aparece una relación persistida de
   ratificaciones (assessor × instrument version, con actor y fecha — la ratificación es
   acto humano, vía CLI que muestra el diff y pide la decisión del delta); la validación
   "al registrarlo" de ADR-0016/0018 se convierte en la ratificación inicial. La forma
   exacta de tablas y comandos la decide el bloque 6. Entradas de cobertura de criteria
   que una versión ya no tiene son inertes para esa versión (como los
   `data_requirements` huérfanos: el linaje no borra).

## Relación con ADR-0016 y ADR-0018

**No los supersede.** De ADR-0016 siguen vigentes la taxonomía `human | automated`, el
assessor como artefacto modular versionado, la invalidación por identidad **del artefacto**
y el instrumento 100% declarativo; este ADR refina su cláusula 3: "declara un instrumento
target (una versión)" pasa a "se debe a un linaje y ratifica versiones". De ADR-0018
siguen vigentes las abstenciones, el estado `not_assessed` y la validación de unión
disjunta; cambia el objeto de esa validación: de una única versión target a cada versión
ratificada.

## Consecuencias

- (+) Muere el churn espurio: una versión nueva del instrumento cuesta a cada assessor una
  ratificación (diff + decisión sobre el delta), no una identidad nueva. La fase de
  calibración de instrumentos (versiones baratas en sucesión) deja de recostar su costo en
  los assessors.
- (+) La calibración transfiere exactamente donde debe — más fiel al principio de
  invalidación por identidad de ADR-0016 que la regla que este ADR refina.
- (+) Queda registrado **quién decidió qué sobre cada delta** (la ratificación es acto con
  actor y fecha), en lugar de quedar implícito en un bump de versión.
- (−) Una relación más que persistir y consultar (ratificaciones) y un comando más de CLI.
- (−) La comparación de texto normativo exige canonicalización estable (comparación
  literal; cualquier retoque de redacción de una `pass_condition` cuenta como cambio y
  pide decisión — falso positivo barato preferible a drift silencioso).
- (−) "Instrumento 1 → 0..N assessors" se lee ahora por linaje; saber qué assessor puede
  evaluar qué versión requiere consultar ratificaciones, no solo `source_config`.

## Alternativas consideradas

- **Mantener el target por versión (ADR-0016/0018 literal)** → rechazada: invalida
  identidad y calibración con código byte-idéntico — churn espurio por el argumento del
  propio ADR-0016.
- **Compatibilidad automática sin ratificación** (criteria nuevos derivan `not_assessed`
  implícito) → rechazada: un criterion nuevo pasaría sin decisión consciente —
  exactamente lo que ADR-0016 §3 quiso impedir — y un bug de omisión vuelve a ser
  indistinguible de una limitación conocida (el argumento de ADR-0018).
- **Abaratar el bump** (auto-generar la versión nueva del assessor con el target
  actualizado) → rechazada: automatiza la ceremonia en vez de eliminarla; sigue
  fragmentando identidad y calibración sin causa real y ensucia el historial de assessors
  con versiones sin cambio.
- **Target por `instrument_id` sin ratificación por versión** → rechazada: drift
  silencioso — el assessor "cubriría" versiones que nunca vio.

## Referencias

ADR-0016 cláusulas 2, 3 y 6 (la cláusula refinada y las que este ADR preserva) · ADR-0018
(abstenciones y `not_assessed`, vigentes; su validación cambia de objeto) · 12-define
§Evaluation Design inv. 1 (linaje de ids — el sustrato) · 13-code §3.5 (la realización que
este ADR enmienda) · el instrumento `learnpack-course-qa-v1` y su fase de calibración (el
caso que expuso el churn) · sesión de análisis de rigidez del versionado (notes/, ciclo
cumplido).
