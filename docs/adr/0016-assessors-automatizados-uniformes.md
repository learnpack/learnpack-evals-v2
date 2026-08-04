# ADR-0016 — Assessors automatizados uniformes: el mecanismo por criterion es interno del assessor

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation ·
Evaluation Design · Identity

## Contexto

El glosario definía cuatro tipos de `EvaluationSource`: `HumanExpert`, `LLMJudge`,
`DeterministicVerifier` e `HybridVerifier`, con `SourceConfiguration` como la config que define
a un `Assessor` de tipo `LLMJudge`. Al diseñar el plan de código del slice 2
(`design/13-code-qa.md`) esa taxonomía mostró tres problemas:

1. **La distinción deterministic/LLM no corta por identidades sino por un espectro.** Un
   "LLM judge" nunca es solo un LLM: siempre es código determinista que orquesta llamadas a un
   modelo. Y dentro de un mismo instrumento, unos criteria son naturalmente computables
   ("al menos 3 objetivos declarados") y otros piden juicio semántico ("cada objetivo usa un
   verbo observable") — el mecanismo idóneo varía **por criterion**, no por instrumento ni por
   "tipo de fuente". El propio glosario lo insinuaba: `HybridVerifier` era "la Hybrid Norm" —
   si el híbrido es la norma, los otros dos son puntos degenerados del espectro.
2. **Tipar al juez por mecanismo fuerza elecciones artificiales**: o se fragmenta la identidad
   del juez por criterion (¿quién produjo *la evaluación*?), o se ata todo el instrumento a un
   mecanismo que no le corresponde.
3. **La realización tentaba a poner la referencia de ejecución dentro del criterion**
   (un `check_spec` apuntando a funciones). Eso rompe que el criterion sea agnóstico de
   fuente: la misma condición debe poder juzgarla un humano, código puro o código con LLM.

## Decisión

**La taxonomía de fuentes se reduce a `human | automated`; todo lo demás es detalle interno
del assessor automatizado.**

1. **Dos tipos, con diferencia estructural real:** los humanos entran por
   assignments/UI/asincronía (ADR-0002/0005, ADR-0015); los automatizados por config +
   ejecución. Cuánto LLM usa un assessor automatizado no define identidad ni tipo — es detalle
   interno de su ejecución por criterion.
2. **El assessor automatizado es un artefacto de software modular y versionado**
   (`{name, version, config}`): un paquete propio con un **mapeo interno
   `criterion_id → ejecutor`**. Cualquier cambio (código, mapeo, modelo, prompt, threshold
   interno) ⇒ versión nueva ⇒ **otra identidad** (la calibración no transfiere — invalidación
   por identidad, como ya regía para `SourceConfiguration`).
3. **Cada assessor automatizado declara un instrumento target** (una versión): se debe a los
   criteria de ese instrumento. Relación: instrumento 1 → 0..N assessors automatizados; los
   humanos no están ligados a ninguno. La cobertura del target se **valida al registrarlo**
   (mapeo completo sobre todos los criteria). Assessors independientes sobre el mismo
   instrumento son comparables — el caso de dispersión/acuerdo que ADR-0005 habilita.
4. **El instrumento queda 100% declarativo.** Nunca referencia ejecutores, checks ni
   mecanismos. Los umbrales normativos viven en la `pass_condition` del criterion (ADR-0010);
   el ejecutor los realiza. Es la misma jugada de ADR-0014 en el otro borde: el lado oferta
   (assessor) declara sus capacidades contra los ids del lado norma (criteria) — el mapeo vive
   en la oferta.
5. **`eligible_sources` del criterion toma valores `{human, automated}`.**
   `SourceConfiguration` se generaliza: es la config de cualquier assessor automatizado.
6. La consistencia entre la condición normativa (texto) y su realización (código) no es
   verificable por tests: la verifica la **capa 2 humana** (ADR-0015) sobre outcomes citados.

## Consecuencias

- (+) Assessors modulares e independientes: dos personas pueden construir enfoques distintos
  para el mismo instrumento sin compartir identidad ni pisarse; comparar sus resultados usa la
  maquinaria existente (repeticiones + dispersión, ADR-0005/0006).
- (+) El instrumento es portable entre assessors (humano hoy, código mañana, LLM después) sin
  tocarlo.
- (+) Desaparece el churn de identidad espurio de una "librería de checks" compartida (donde
  cualquier cambio invalidaba a todos los jueces a la vez).
- (+) La cadena de provenance no cambia: `assessorId` sigue siendo la clave, para humanos y
  automatizados.
- (−) Un criterion nuevo en el target exige versión nueva del assessor (enseñarle al corrector
  a corregir una pregunta nueva ES cambiar al corrector). Correcto pero laborioso; mitigable
  con utilidades compartidas bottom-up (con la disciplina de subir versión al tocarlas).
- (−) La propiedad "determinístico" (reproducibilidad bit a bit, sin ruido de muestreo) deja
  de ser un tipo; cuando la calibración necesite distinguirla (self-consistency, ADR-0006
  `[futuro]`), se lee de la config del assessor.
- (−) El GLOSSARY debe reescribir su eje Source; `LLMJudge`, `DeterministicVerifier` y
  `HybridVerifier` pasan a la tabla de equivalencias como vocabulario de industria/legado.

## Alternativas consideradas

- **Mantener la taxonomía de cuatro tipos** → rechazada: tipa por mecanismo lo que varía por
  criterion; fuerza identidades artificiales y no aporta ninguna distinción estructural que
  `human | automated` no cubra.
- **Referencia de ejecución (`check_spec`) dentro del criterion** → rechazada: rompe el
  criterion agnóstico de fuente y arrastra vocabulario del ejecutor a los datos del
  instrumento.
- **Una librería de checks compartida como único assessor determinístico** → rechazada:
  cualquier cambio en cualquier función cambiaba la identidad de todos los jueces (invalidación
  espuria), e impedía la experimentación independiente de assessors en paralelo.
- **Mini-DSL de condiciones interpretado** → rechazada por ahora: exige diseñar, parsear,
  validar y versionar un lenguaje propio sin consumidor presente; los errores pasan de "test
  que falla" a "expresión mal interpretada en runtime". Trigger de reconsideración: que la
  autoría quede bloqueada esperando código de ejecutores.

## Referencias

Separación instrumento/rater en psicometría (inter-rater reliability; calibración de
correctores) · el problema de *judge drift* y "version your judge" en la industria de
LLM-evals · `design/13-code-qa.md` §3.5 (realización) · discusión completa en la sesión de
diseño del plan de código (notes/, ciclo cumplido).
