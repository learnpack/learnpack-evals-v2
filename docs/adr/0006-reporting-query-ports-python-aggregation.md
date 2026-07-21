# ADR-0006 — Reporting: composición por query ports + agregación en Python

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** Reporting (supporting-generic)

## Contexto
Reporting lee datos de todos los módulos (scores, evaluations, assignments, contents, assessors).
`07-define` (escrito antes) decía "vistas/queries SQL sobre las tablas", pero después se endureció
la regla de aislamiento (sin JOINs cross-módulo; import de `modules/*/infrastructure` prohibido)
hasta volverla un test de arquitectura. Hay que resolver la contradicción y fijar cómo agrega
Reporting.

## Decisión
1. **Composición vía query ports + agregación en Python.** Cada módulo dueño expone lo suyo en su
   `public.py` (evaluation suma una query de scores); Reporting compone y calcula media/dispersión
   en Python. Cero tablas nuevas; respeta el aislamiento. A escala MVP (~50 cursos × 3 SMEs × 5
   criteria ≈ 750 scores) el costo es nulo. Usar queries **batch** para evitar N+1.
2. **Inter-rater por criterion = dispersión simple:** desvío estándar + diferencia absoluta media
   entre pares + % de acuerdo exacto. Interpretable con 2-3 raters, respeta la escala ordinal 1-5,
   sin dependencias nuevas. Suficiente para detectar criteria/cursos conflictivos al construir el
   golden.
3. **Repeticiones del mismo assessor:** colapsar a **la más reciente** por
   `(assessor, content, rubricVersion)` (la definición de repetición de ADR-0005 — **no** por
   assessor solo: eso colapsaría cursos distintos del mismo evaluador), porque una re-evaluación
   humana es una corrección que supersede; y recién ahí promediar entre assessors — consistente
   con el quórum, que cuenta assessors distintos.

## Consecuencias
- (+) Respeta la regla de aislamiento (Reporting extraíble; nadie acopla su schema).
- (+) Sin maquinaria de proyecciones ni consistencia eventual → reportes exactos para el demo.
- (+) Thin, acorde a supporting-generic (`04-strategize`).
- (−) La agregación en Python no escala a millones de filas — irrelevante al volumen MVP.

## `[futuro]`
- **Proyecciones CQRS alimentadas por eventos** (read-model tables) cuando el volumen/latencia lo
  pidan — el modelo objetivo de Reporting.
- **Métrica formal de acuerdo** (Krippendorff's α: N raters variables, ordinal) cuando haya que
  calibrar fuentes automáticas.
- **Muestreo automático intencional** (p.ej. `LLMJudge` ×N): colapsar por **media** por assessor +
  reportar **dispersión intra-assessor** (self-consistency) por separado — agregación distinta,
  para un propósito distinto (calibración), no la del MVP humano.

## Alternativas
- **Vistas SQL con JOINs cross-módulo** (lo que decía 07-define) → rechazada: rompe el aislamiento,
  vuelve a Reporting un módulo privilegiado que impide cambios de schema ajenos, exigiría exceptuar
  Reporting del test de arquitectura.
- **Proyecciones CQRS por eventos ya en el MVP** → rechazada: over-engineering para el volumen
  actual; consistencia eventual innecesaria.
