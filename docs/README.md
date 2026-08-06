# docs — índice

Diseño de un sistema para **evaluar la calidad pedagógica de contenido educativo generado por
IA**, siguiendo el DDD Starter Modelling Process (ddd-crew).

## Cómo está organizada la documentación

Cada documento tiene un **contrato de mantenimiento** distinto, y la ubicación lo declara:

| Dónde | Clase | Contrato |
|---|---|---|
| **raíz de `docs/`** | reference | **Siempre cierto de `main`.** Cambia en el mismo commit que el código. Sin fechas ni estado. |
| `docs/adr/` | decision | **Inmutable.** Un ADR no se edita: se supersede con uno nuevo. |
| `docs/design/` | snapshot | **Congelado.** Qué pensamos y por qué, en su momento. No se mantiene. |
| `../backend/README.md`, `../frontend/README.md` | reference | Runbook operativo, al lado del código que opera. |
| `../STATUS.md` | estado | **El único lugar con estado fechado.** Se reescribe entero. |
| `notes/` (gitignored) | working | Efímero. Al cerrar la tarea: se promueve o se borra. |

Regla para decidir si algo va a la raíz de `docs/`: *¿va a seguir siendo cierto dentro de seis
meses sin que nadie lo toque?* Si no, no va ahí. Las reglas completas —incluido qué hacer con una
nota cuando la tarea termina— están en `../CLAUDE.md`, sección **Documentación**.

## Cómo leer (para Claude Code)
1. `../CLAUDE.md` — no negociables (raíz del repo).
2. `ARCHITECTURE.md` — Dependency Rule, hexagonal, aislamiento de módulos, events-first.
3. `GLOSSARY.md` — ubiquitous language (inglés). **Los nombres del código salen de acá.**
4. `design/` — el porqué de cada límite (pasos 01–07) y el plan del MVP (08).

## Contenido

**Vigente (reference)**
- `ARCHITECTURE.md` — invariantes no negociables.
- `GLOSSARY.md` — lenguaje ubicuo.

**Decisiones (`adr/`, inmutables)**
`0001` metadata abierta *(superseded por 0017)* · `0002` campañas/assignments/quórum ·
`0003` Postgres + events · `0004` Clerk · `0005` identidad de Evaluation + versionado de
contenido · `0006` Reporting por query ports · `0007` bootstrap de admin (allowlist de
aprovisionamiento) · `0008` modo local (correr sin Clerk ni Neon) · `0009` extracción sin
inferencia · `0010` criteria como condiciones verificables · `0011` sin score agregado único ·
`0012` génesis de instrumentos · `0013` diseño con ECD-lite · `0014` vocabulario en evidence
models · `0015` referencia humana en dos capas · `0016` assessors automatizados uniformes ·
`0017` la superficie declarada es el paquete · `0018` cobertura declarada del assessor +
`not_assessed`.

**Snapshots (`design/`, congelados)**
Pasos 01–08 del proceso de modelado + `research/`. Ver `design/README.md`.

**Assets** (no son documentación)
- `seed/rubric-v1.json` — seed de la rubric del MVP; lo consume `app.cli seed`.

## Stack del MVP (confirmado)
Next.js/Tailwind/shadcn en **Netlify** · **FastAPI** en **Render Starter** · Postgres/pgvector
en **Neon** · **Clerk** (invite-only) como identidad. Detalle en `design/08-code.md`.

## El norte, en dos frases
- **Core = evaluación pedagógica** (producir juicios de calidad multi-fuente, multi-criterio,
  con provenance y calibrables). **La calibración NO es el core.**
- **Dos horizontes:** el modelo objetivo está documentado completo; **el MVP es una rebanada
  fina** (evaluación humana; store Postgres/Neon, deploy económico).
