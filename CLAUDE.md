# CLAUDE.md

Guía para generar el código de este repositorio. **Leer `docs/` antes de escribir código.**

## Orden de lectura
1. `docs/ARCHITECTURE.md` — invariantes no negociables (empezar acá).
2. `docs/GLOSSARY.md` — ubiquitous language (los nombres del código salen de acá).
3. `docs/design/01-align.md` … `docs/design/05-connect.md` — el diseño estratégico (por qué de
   cada límite).
4. `docs/design/07-define.md` — diseño táctico por contexto (agregados, invariantes). *(en curso)*
5. `STATUS.md` — en qué punto está el desarrollo **hoy**.

## No negociables (resumen de ARCHITECTURE.md)
- **Dependency Rule:** las dependencias apuntan **solo hacia adentro**
  (Frameworks → Adapters → Application → Domain). El **Domain es Python puro**: sin FastAPI,
  SQLAlchemy, LiteLLM ni I/O.
- **Ports & adapters:** los ports se definen en Application/Domain; los adapters (Postgres/Neon,
  Clerk, LiteLLM) se implementan afuera y se inyectan.
- **Aislamiento de módulos:** los módulos hablan por **domain events + DTOs de query**; nunca
  se importa el dominio interno de otro módulo. ACL en los bordes externos (LearnPack, LLM).
- **Events-first:** el estado evoluciona por domain events; las policies reaccionan; sin
  comandos cruzados. En el MVP un evento es un `INSERT` en la tabla `events` (outbox, ADR-0003).

## Documentación — dónde escribir qué (regla dura)

Cada documento tiene un **contrato de mantenimiento**, y la ubicación lo declara. Antes de
escribir un `.md`, elegir clase:

| Clase | Dónde | Contrato |
|---|---|---|
| **reference** | raíz de `docs/`, `backend/README.md`, `frontend/README.md` | **Siempre cierto de `main`.** Se actualiza en el **mismo commit** que el código que lo vuelve falso. |
| **decision** | `docs/adr/` | **Inmutable.** Nunca se edita un ADR: se escribe uno nuevo que lo supersede. |
| **snapshot** | `docs/design/` | **Congelado.** No se mantiene ni se corrige, aunque el sistema lo contradiga. |
| **working** | `notes/` (gitignored) | Efímero. Al cerrar la tarea **se promueve o se borra**. |

Reglas que no se negocian:

1. **Nada de estado fuera de `STATUS.md`.** Ni "ya está hecho", ni "falta X", ni "N tests en
   verde", ni "✔ verificado el 30-jul", ni fechas de cuándo se probó algo. En un doc reference
   se escribe **cómo funciona y por qué**, en presente y sin fecha. El estado va a `STATUS.md`,
   que se reescribe entero.
2. **Todo análisis, plan o investigación nace en `notes/`** — no en `docs/`. Incluye lo que
   generes vos (planes de implementación, auditorías, comparativas).
3. **Al terminar la tarea, cada nota tiene cuatro salidas y solo cuatro:** fue una *decisión con
   alternativas descartadas* → ADR · fue una *regla o instrucción* → se funde en un reference
   existente (no un archivo nuevo) · fue un *análisis de un momento* → se congela en
   `docs/design/` · **ninguna de las anteriores → se borra**.
4. **Test para admitir algo en reference:** ¿va a seguir siendo cierto dentro de seis meses sin
   que nadie lo toque? Si no, no va ahí.
5. **Lo operativo vive al lado del código que opera** (READMEs de `backend/`/`frontend/`);
   `docs/` es solo lo transversal.
6. **Antes de crear un `.md` nuevo, buscar dónde fundirlo.** Un doc nuevo se justifica por tener
   un ciclo de vida propio, no por ser un tema nuevo.

## Convenciones
- **Ubiquitous language y código en inglés**; docs y comentarios de negocio pueden ir en
  español. Usar exactamente los nombres del `docs/GLOSSARY.md`.
- Distinguir siempre: `EvaluationSource` (tipo/port) vs. `Assessor` (instancia concreta) ·
  `ComputedMetric` (medición) vs. `CriterionScore` (juicio) · `rubricVersion` inmutable.

## Dos horizontes (crítico)
- El **modelo objetivo** está documentado completo, pero **el MVP es una rebanada fina**
  (evaluación humana, deploy económico). Ver alcance en `docs/design/01-align.md` y
  `docs/design/04-strategize.md`.
- **Mantener el MVP liviano**: no construir fuentes automáticas, métricas ni calibración
  (todo `[futuro]`). Respetar los límites documentados sin agregar ceremonia prematura.
- Ante la duda: preferir lo que dice la doc del modelo objetivo para no cerrar puertas, pero
  implementar solo el slice del MVP.

## Stack
**MVP (confirmado):** Next/Tailwind/shadcn en Netlify · FastAPI en Render Starter ·
Postgres/pgvector en Neon · Clerk (invite-only). Ver `docs/design/08-code.md`, ADR-0003 y
ADR-0004.
**Target `[futuro]`:** LiteLLM/OpenRouter y LangGraph (solo si hace falta orquestar agentes) —
no se usan en el MVP.
