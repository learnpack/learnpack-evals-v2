# ADR-0021 — El `fail` derivado de ausencia: outcome sin cita, con origen registrado

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation

## Contexto

Tres reglas vigentes chocan en un caso que el primer instrumento hace inevitable:

1. **ADR-0009**: sin cita no es evidencia — todo veredicto apunta a texto verbatim.
2. **ADR-0010 / 12-define**: cada criterion declara `on_missing_evidence` — la consecuencia
   de que el dato requerido esté ausente del contenido. Con `fail`, **la ausencia misma es
   el defecto** (ADR-0009 §4: la ausencia es un hallazgo de primera clase). Seis de los once
   criteria de `learnpack-course-qa-v1` lo declaran así; su caso más importante es
   exactamente ese ("No objectives declared at all — the generator omitted them").
3. **ADR-0018 §5 / 13-code §3.5**: el CHECK de `criterion_outcomes` exige cita en todo
   `pass`/`fail` ("scored exige cita").

Una entrada `absent` del profile **no tiene cita por construcción** (no se puede citar texto
que no existe; el CHECK de `profile_entries` lo garantiza). El `fail` que la derivación
mecánica produce de ella es, entonces, un `fail` sin cita — y la regla 3 lo vuelve
**imposible de persistir**. La letra de ADR-0018 §5, escrita pensando en outcomes producidos
por ejecutores, bloquea el desenlace que ADR-0009 §4 y ADR-0010 exigen.

## Decisión

**El origen del outcome se registra en la fila (`derived`), y la exigencia de cita se
condiciona a ese origen.**

1. `criterion_outcomes` gana **`derived boolean not null default false`**: `true` = el
   outcome lo produjo la derivación mecánica (ausencia con `on_missing_evidence='fail'`);
   `false` = lo produjo un ejecutor (humano o automatizado) mirando la evidencia.
2. Los CHECKs pasan a ser: **`pass` ⇒ cita y no derivado** (un pass es siempre alguien
   afirmando algo que vio — la mecánica nunca deriva pass) · **`fail` ⇒ cita O derivado** ·
   los tres estados no-scored siguen sin exigir cita.
3. **El fail derivado produce finding** — la ausencia es el hallazgo accionable — con
   `quote` null y `failure_mode` mecánico `"required data absent: <data_requirement_ids>"`,
   nunca uno elegido de los declarados (elegir uno sería fingir que un ejecutor juzgó). Su
   evidencia es la entrada `absent` del profile: el registro citable de que el adapter miró
   y no había, verificable contra el paquete.
4. Los demás derivados mecánicos (`not_applicable`, `no_evidence`, `not_assessed`) también
   llevan `derived=true` — el origen queda uniforme y queryable (útil para `evidence_basis`
   y los caveats de reports).

## Relación con ADR-0018 y ADR-0009

**Refina ADR-0018 §5** (no lo supersede): la cobertura exacta sobre cinco estados y todo lo
demás sigue igual; "scored exige cita" pasa a "scored **ejecutado** exige cita". **Realiza
ADR-0009 §4**: la ausencia es un hallazgo de primera clase también en la persistencia. La
garantía de ADR-0009 queda intacta donde importa: todo lo que un ejecutor afirma sigue
exigiendo cita verbatim.

## Consecuencias

- (+) El caso central de seis criteria reales (generador que omite lo que debía declarar) es
  persistible y produce su finding accionable.
- (+) `derived` distingue en datos "lo juzgó alguien" de "lo derivó la mecánica" — la capa 2
  humana (ADR-0015) puede filtrar qué revisar.
- (−) Un finding sin cita es una excepción a la forma general; los reports deben mostrarlo
  con su causa ("dato ausente") para que no se lea como finding incompleto.
- (−) El GLOSSARY ajusta la frase "desenlace + cita" donde implique cita incondicional.

## Alternativas consideradas

- **Fail derivado sin finding** → rechazada: el claim se refuta pero la lista accionable
  pierde la señal más útil justo en el caso "la ausencia es el hallazgo".
- **Citar la entrada `absent` como quote sintética** ("<absent: learning_objectives>") →
  rechazada: una cita fabricada satisface el CHECK mintiendo — el vacío disfrazado de texto.
- **Mapear ausencia+`fail` a `no_evidence`** → rechazada: anula `on_missing_evidence='fail'`
  (ADR-0010) y esconde el defecto que el criterion existe para atrapar.

## Referencias

ADR-0009 (§4: la ausencia es un hallazgo) · ADR-0010 (`on_missing_evidence`) · ADR-0018 §5
(la regla refinada) · 13-code §3.5 (el CHECK que este ADR corrige) · 12-define §Content
Profiling inv. 3 (la entrada `absent` explícita — la evidencia del fail derivado) ·
`learnpack-course-qa-v1` (los seis criteria con `on_missing_evidence: fail`).
