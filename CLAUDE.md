# CLAUDE.md

Guía para generar el código de este repositorio. **Leer `docs/` antes de escribir código.**

## Orden de lectura
1. `docs/ARCHITECTURE.md` — invariantes no negociables (empezar acá).
2. `docs/GLOSSARY.md` — ubiquitous language (los nombres del código salen de acá).
3. `docs/01-align.md` … `docs/05-connect.md` — el diseño estratégico (por qué de cada límite).
4. `docs/07-define.md` — diseño táctico por contexto (agregados, invariantes). *(en curso)*

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

## Convenciones
- **Ubiquitous language y código en inglés**; docs y comentarios de negocio pueden ir en
  español. Usar exactamente los nombres del `GLOSSARY.md`.
- Distinguir siempre: `EvaluationSource` (tipo/port) vs. `Assessor` (instancia concreta) ·
  `ComputedMetric` (medición) vs. `CriterionScore` (juicio) · `rubricVersion` inmutable.

## Dos horizontes (crítico)
- El **modelo objetivo** está documentado completo, pero **el MVP es una rebanada fina**
  (evaluación humana, deploy económico). Ver alcance en `01-align.md` y `04-strategize.md`.
- **Mantener el MVP liviano**: no construir fuentes automáticas, métricas ni calibración
  (todo `[futuro]`). Respetar los límites documentados sin agregar ceremonia prematura.
- Ante la duda: preferir lo que dice la doc del modelo objetivo para no cerrar puertas, pero
  implementar solo el slice del MVP.

## Stack
**MVP (confirmado):** Next/Tailwind/shadcn en Netlify · FastAPI en Render Starter ·
Postgres/pgvector en Neon · Clerk (invite-only). Ver `08-code.md`, ADR-0003 y ADR-0004.
**Target `[futuro]`:** LiteLLM/OpenRouter y LangGraph (solo si hace falta orquestar agentes) —
no se usan en el MVP.
