# docs — índice

Diseño de un sistema para **evaluar la calidad pedagógica de contenido educativo generado por
IA**, siguiendo el DDD Starter Modelling Process (ddd-crew). Documentos vivos (v0).

## Cómo leer (para Claude Code)
1. `../CLAUDE.md` — no negociables (raíz del repo).
2. `ARCHITECTURE.md` — Dependency Rule, hexagonal, aislamiento de módulos, events-first.
3. `GLOSSARY.md` — ubiquitous language (inglés). **Los nombres del código salen de acá.**
4. Pasos 01–07 en orden.

## Estado de los pasos

| Doc | Paso | Estado |
|---|---|---|
| `01-align.md` | Align | ✔ cerrado |
| `02-discover.md` | Discover (Big-Picture EventStorming) | ✔ cerrado |
| `03-decompose.md` | Decompose (subdominios) | ✔ cerrado |
| `04-strategize.md` | Strategize (Core Domain Chart) | ✔ cerrado |
| `05-connect.md` | Connect (Context Map) | ✔ cerrado |
| `06-organise.md` | Organise | ✔ placeholder |
| `07-define.md` | Define (Bounded/Aggregate Design Canvas) | ✔ MVP slice completo · modelo objetivo pendiente |
| `08-code.md` | Code (plan de implementación del MVP) | ✔ listo para implementar |

## Stack del MVP (confirmado)
Next.js/Tailwind/shadcn en **Netlify** · **FastAPI** en **Render Starter** · Postgres/pgvector
en **Neon** · **Clerk** (invite-only) como identidad. Detalle en `08-code.md`.

## Transversales
- `ARCHITECTURE.md` — invariantes no negociables.
- `GLOSSARY.md` — lenguaje ubicuo.
- `research/deterministic-evaluation-landscape.md` — insumo (evaluación determinística/híbrida).
- `adr/` — decisiones: 0001 metadata abierta · 0002 campañas/assignments · 0003 Postgres+events ·
  0004 Clerk · 0005 identidad de Evaluation + versionado de contenido · 0006 Reporting por query
  ports · 0007 bootstrap de admin (allowlist de aprovisionamiento).
- `seed/rubric-v1.json` — seed de la rubric del MVP.
- `diagrams/` — diagramas exportados del diseño (opcional, versionables).

## El norte, en dos frases
- **Core = evaluación pedagógica** (producir juicios de calidad multi-fuente, multi-criterio,
  con provenance y calibrables). **La calibración NO es el core.**
- **Dos horizontes:** el modelo objetivo está documentado completo; **el MVP es una rebanada
  fina** (evaluación humana; store Postgres/Neon, deploy económico).
