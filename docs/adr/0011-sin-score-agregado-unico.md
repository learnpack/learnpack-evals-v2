# ADR-0011 — Sin score agregado único: el resultado es un perfil por criterion

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Pedagogical Evaluation / Reporting

## Contexto

Hoy Reporting calcula, además del promedio por criterion, un **promedio general** por contenido y
uno global (`overall_average` / `global_average` en
`backend/app/modules/reporting/application/aggregation.py`). Es la forma más intuitiva de
responder "¿qué tan bueno es este curso?".

Tres problemas la vuelven insostenible al abrir el motor:

1. **La calidad pedagógica no tiene una fórmula de composición universalmente aceptada.** Promediar
   criteria fundados en marcos distintos (Bloom, Biggs, Merrill, Schmidt) supone que son
   conmensurables y equiponderados. No hay nada que lo justifique.
2. **Un promedio esconde exactamente lo que interesa.** Un curso con objetivos excelentes y cero
   alineación puede empatar con uno mediocre parejo. La información accionable —qué está mal— se
   pierde en el número.
3. **Con desenlaces tri-estado (ADR-0010) el promedio deja de estar definido.** ¿Qué valor tiene un
   `not_applicable`? ¿Y un `no_evidence`? Cualquier elección silenciosa miente: si "sin evidencia"
   cuenta como mínimo, se confunde *ausente* con *malo*; si se excluye, un curso vacío saca nota
   perfecta.

Tres fuentes maduras e independientes evitan el número único: `k12-teacher-skills` —*"track
per-criterion pass rates rather than aggregates, since aggregate scores mask specific gaps"*—; las
Achieve OER Rubrics, ocho rubrics con la regla explícita de puntuarse **independientemente**; y
Quality Matters, que ni siquiera con pesos usa un promedio: usa umbral **más** standards
obligatorios que deben cumplirse todos.

## Decisión

**El resultado de evaluar un contenido es un perfil por criterion, no un score.**

1. **No se publica un score único que agregue criteria distintos**, ni por contenido ni global.
   Se elimina `overall_average` / `global_average`.
2. **Se sigue agregando *el mismo* criterion entre assessors.** Promediar el criterion C sobre 3
   evaluadores es legítimo y es lo que la dispersión inter-rater necesita. Lo prohibido es
   colapsar **entre criteria distintos**.
3. **Todo resultado se reporta junto a su cobertura**: cuántos criteria se evaluaron, cuántos no
   aplicaban, cuántos quedaron sin evidencia. **Un resultado sin cobertura es engañoso.**
4. **Reglas del denominador:** `not_applicable` queda **fuera**; `no_evidence` queda **dentro** —si
   se excluyera, un curso sin nada evaluable obtendría el mejor resultado posible.
5. **Comparar contenidos se hace criterion por criterion**, o por subconjuntos declarados
   explícitamente (p. ej. una dimensión), nunca por un total.

## Relación con ADR-0006

**No lo supersede.** ADR-0006 decide *el mecanismo* de Reporting (composición por query ports +
agregación en Python) y la dispersión inter-rater por criterion; todo eso sigue vigente. Esta ADR
decide una cuestión de modelo que ADR-0006 dejó implícita: **qué es lícito agregar**. El promedio
por criterion y la dispersión de ADR-0006 se conservan; el promedio general se retira.

## Consecuencias

- (+) El reporte pasa a decir algo accionable: *qué* falla, no *cuánto* falla en abstracto.
- (+) Compatible con el tri-estado de ADR-0010 sin decisiones silenciosas.
- (+) Evita que un número aparentemente objetivo respalde una composición que nadie fundamentó.
- (−) **Cambia la consola de admin ya construida**, que hoy muestra promedio por curso y global.
  Hay que rehacer esa vista y sus tests.
- (−) Se pierde el ranking trivial de cursos. Es intencional: ese ranking suponía una
  conmensurabilidad que no existe. Si más adelante hace falta ordenar, deberá justificarse con un
  esquema explícito (pesos, *gates*) y su propia ADR.
- (−) Un perfil es más difícil de comunicar que un número. Es un problema de presentación, y es el
  correcto de tener.

## `[futuro]`

- **Gates obligatorios estilo Quality Matters** (criteria que, si fallan, invalidan el conjunto sin
  importar el resto). Encajan con el perfil y no requieren promedio, pero exigen decidir cuáles son
  esenciales — decisión pedagógica que hoy no tenemos fundamento para tomar.
- **Pesos por criterion.** Sin datos que los justifiquen, serían arbitrarios con apariencia de
  rigor.

## Alternativas consideradas

- **Mantener el promedio general como "indicativo"** → rechazada: todo número publicado se usa como
  autoritativo, por más etiquetas que lleve.
- **Score único con pesos** → rechazada por ahora: no tenemos base empírica para los pesos, y sin
  ella el peso es una opinión disfrazada de medición. Reconsiderable cuando exista el golden.
- **Score por dimensión** (5 números en vez de 1) → parcialmente aceptada en espíritu: agrupar por
  dimensión es una vista legítima, pero requiere el mismo argumento de conmensurabilidad dentro de
  la dimensión. Se admite como agrupación de presentación, no como valor publicado.
</content>
