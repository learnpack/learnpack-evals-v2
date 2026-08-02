# ADR-0013 — Diseño de evaluaciones con ECD-lite: claims como eje

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Rubric/Instrument Authoring ·
Pedagogical Evaluation · Reporting

## Contexto

No había proceso de diseño de instrumentos: los criteria se escribían directo, y las decisiones
estructurales —qué se pretende medir, cuánta evidencia basta, qué invalidaría una observación—
quedaban tácitas. Es el diagnóstico exacto que ECBD (ACL 2024) hace de los benchmarks de NLP:
diseño apoyado en "supuestos tácitos y no testeados sobre qué se pretende medir".

**Evidence-Centered Design** (Mislevy et al.) estructura una evaluación como **argumento
evidencial**: *claim ← acumulación de evidencia ← observables ← identificación de evidencia ←
work product ← tarea*, con **warrants** (Toulmin) que licencian cada inferencia y **explicaciones
alternativas** que hay que poder descartar. ECBD demostró que ECD se transfiere a evaluar
sistemas de IA. La aplicación a calidad pedagógica de contenido generado por IA no existe
publicada; este sistema ocupa esa intersección: **el examinado es el generador; cada contenido es
un work product suyo**.

Los ADRs 0009/0010/0011 ya tienen forma ECD sin nombrarla: evidencia citada = identificación de
evidencia; condiciones verificables = scoring rules; no colapsar a un número = restricción sobre
la acumulación.

## Decisión

**Se adopta ECD-lite: cuatro piezas, no una reescritura.**

1. **`Claim` como artefacto de primera clase.** Registro de claims: una frase + evidencia
   requerida + warrant (framework) + explicaciones alternativas. Si un claim necesita más de
   media página, está mal descompuesto. **El diseño corre hacia atrás**: claims → evidencia →
   observables → requisitos de extracción. La demanda de datos del sistema entero se origina acá
   (ver ADR-0014).
2. **Dos granos de claims: contenido y generador.** Además del juicio por contenido, se acumula
   evidencia **a través de contenidos** para afirmar patrones del generador ("produce
   sistemáticamente objetivos vagos en cursos introductorios"). El claim a nivel generador es el
   producto central del QA interno.
3. **Explicaciones alternativas por diseño.** Cada claim enumera *por adelantado* qué podría
   producir la misma observación sin que el claim aplique: extracción fallida, formato atípico,
   criterion ambiguo. Formaliza el diagnóstico del bucle de mejora del instrumento y el canal de
   impugnación de hallazgos.
4. **Assembly explícito: cuánta evidencia basta, por claim, decidido en diseño.** En el camino
   automático reemplaza la noción de quórum; replicar assessors es una forma de fortalecer
   evidencia, cobertura es otra. **No supersede ADR-0002**: el quórum humano sigue rigiendo las
   campañas con evaluadores humanos. Compatible con ADR-0006 (self-consistency ≠ inter-rater).

**El informe cambia de naturaleza:** claims con estatus evidencial —`soportado / refutado /
evidencia insuficiente`— con los findings organizados **bajo el claim que comprometen**. El
tri-estado por criterion (ADR-0010) se propaga un nivel arriba por la misma lógica.

**Guardas:**
- Sin maquinaria estadística (IRT, redes bayesianas): la acumulación es simple y explícita.
- **Prohibido "% de claims soportados"** como score — ADR-0011 aplica igual un nivel arriba: un
  claim es una aserción cualitativa respaldada por evidencia específica, no un promedio.
- Sin renombrar artefactos existentes al por mayor: la adopción vale por las cuatro piezas.

## Consecuencias

- (+) Cabos sueltos encuentran casa formal: la "referencia contextual" del `ScoringPolicy` es una
  **variable del task model**; la priorización de hallazgos sale de su claim; el *designed-for*
  (ADR-0012) se realiza como **task model binding** por tipo de contenido, dejando claims y
  evidence models portables.
- (+) `Quality`/`PedagogicalDimension` ascienden de reference data a **variables del modelo del
  examinado**: los claims son afirmaciones sobre ellas.
- (+) La **selección del contentSet se vuelve decisión de diseño** (content module de ECBD): "para
  evidencia de progresión, el set necesita cursos con prerrequisitos encadenados". No cruza el
  límite del sistema — no generamos; elegimos qué evaluar.
- (−) Un artefacto más que mantener (el registro de claims). Barato si se respeta el límite de
  media página.
- (−) Exige disciplina para mantenerse *lite*: la tentación de formalizar de más es real.

## Alternativas consideradas

- **Seguir con diseño rubric-first, sin claims** → rechazada: supuestos tácitos sin argumento de
  validez, y —decisivo— sin lugar para afirmaciones a nivel generador, que son el producto del QA
  interno.
- **ECD completo** (CAF formal, modelos de medición) → rechazada: peso injustificado a esta
  escala; el valor está en el argumento explícito, no en la maquinaria psicométrica.
- **Adoptar ECBD entero (cinco módulos)** → rechazada: ceremonia específica de benchmarks
  públicos; se toma el núcleo conceptual que comparte con ECD.

## Referencias

ECBD (https://aclanthology.org/2024.acl-long.861/) · Mislevy, Implications of ECD
(https://csaa.wested.org/wp-content/uploads/2020/01/2006_Implications_of_Evidence_Centered_Design_for_Educational_Testing.pdf) ·
identificación vs. acumulación de evidencia (https://files.eric.ed.gov/fulltext/EJ1115353.pdf) ·
detalle del razonamiento y mapeo completo en `notes/genesis-instrumentos-y-ecd.md`.
</content>
