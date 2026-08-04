# STATUS

**El único lugar del repo con estado fechado.** Se **reescribe** entero cuando cambia algo; no se
apila historia (para eso está git). Si encontrás estado en cualquier otro documento —"ya está
hecho", "falta X", "N tests en verde", "verificado el tal día"— está en el archivo equivocado y
va acá.

_Última actualización: 2026-08-04._

## Dónde estamos

**Slice 1 (MVP humano): completo y verificado en local; falta el deploy.
Slice 2 (motor de QA de generadores): en implementación por bloques — 5 de 7 hechos.**

El repo se puede correr **sin cuentas ni nube** (modo local, ADR-0008): ver el quickstart del
`README.md` de la raíz.

### Slice 1 — MVP

| Bloque (`docs/design/08-code.md` §12) | Estado |
|---|---|
| 1. Scaffolding + migraciones + seed | ✔ |
| 2. identity + content_registry | ✔ |
| 3. rubric_authoring + evaluation + orchestration | ✔ |
| 4. golden_dataset + reporting | ✔ |
| 5. frontend (evaluador + consola admin) | ✔ |
| Deploy (§10: Render + Netlify) | ✗ pendiente |

### Slice 2 — en implementación por bloques

- **Diseño:** serie `docs/design/09…12` + ADRs 0009–0015 (promovido antes).
- **Plan de código:** **`docs/design/13-code-qa.md`** (promovido) + **ADR-0016** (assessors
  automatizados uniformes). GLOSSARY actualizado (eje Source `human | automated`;
  `Sufficiency` ex assembly); ARCHITECTURE y CLAUDE.md re-apuntados.

| Bloque (`13-code-qa.md` §9) | Estado |
|---|---|
| 1. CI (workflow + mypy scoped a módulos nuevos) | ✔ |
| 2. Renames + retiro de promedios (ADR-0011) | ✔ |
| 3. Evaluand Registry ensanchado | ✔ |
| 4. Evaluation Design (instrumento + primer YAML real) | ✔ |
| 5. Content Profiling (adapter LearnpackV1 + visor) | ✔ |
| 6. Evaluation automático (primer assessor) | ✗ |
| 7. Evaluation Studies thin | ✗ |

**Modo de trabajo acordado:** rama + PR por bloque, con nombres de ramas y commits que
describen **el cambio** (feature/fix), nunca etapas del plan; Claude commitea solo dentro de
las ramas de trabajo; Marta revisa y mergea. Cada PR con la suite completa en verde.
(`13-code-qa.md` §8 menciona un esquema de nombres viejo — snapshot congelado, no se corrige.)

**Input pendiente del equipo:** revisar y editar el borrador del primer instrumento
(`docs/seed/instruments/learnpack-course-qa-v1.yaml` — 3 claims / 6 criteria, redactado como
asistencia) y **publicarlo** cuando el equipo lo haga suyo
(`python -m app.cli publish-instrument --id learnpack-course-qa-v1 --email <admin>` o
`POST /admin/instruments/{id}/publish`). Hasta entonces queda en `draft` — la publicación es
acto humano (12-define, invariante 5). Los `data_requirement` ids minteados
(`learning_objectives`, `target_audience`, `prerequisites`, `practice_exercises`) son el
contrato contra el que el adapter `LearnpackV1` (bloque 5) declara sus capacidades.

**Segundo input pendiente del equipo (bloque 5):** revisar las muestras de profile
(`/admin/profiles` o `app.cli profile-content`) y **aceptar la extracción** cuando el equipo
confíe en ella (`python -m app.cli accept-extraction --package-format LearnpackV1 --email
<admin>`). Hasta entonces el perfilado automático al registrar contenido queda desarmado —
la aceptación es acto humano (ADR-0012); `seed-demo` la auto-acepta solo en modo local.

## Verificado

- **Suite backend en verde: 267 tests** contra Postgres local (~12 s). Requiere
  `docker compose up -d` en `backend/`; sin la DB levantada la suite da error, no skip.
- **Modo local** (ADR-0008) probado de punta a punta: `seed-demo` idempotente y con `--reset`
  (ahora también importa el draft del instrumento, acepta la extracción `LearnpackV1` y
  perfila los cursos demo — con `practice_exercises: absent`, el showcase de ADR-0009),
  `/me` y `/dev/identities` respondiendo con `X-Dev-User`, y el frontend compilando **sin
  ninguna clave de Clerk**.
- **Typecheck del frontend** limpio (`npx tsc --noEmit`).
- **Identidad Clerk end-to-end**: JWT template con `email`/`name`, invite-only, admin y evaluador
  entrando con el rol correcto. El runbook de `backend/README.md` ya se corrió en el entorno de
  desarrollo.
- **iframe del contenido** (riesgo abierto en `docs/design/08-code.md` §8): probado con una
  `consumable_url` real de LearnPack, **embebe bien**. El fallback "abrir en pestaña nueva" se
  mantiene porque depende del sitio de cada curso.

## Abierto

- **Deploy**: backend a Render, frontend a Netlify, `ALLOWED_ORIGINS` cruzado, y repetir el
  runbook de Clerk en la instancia de producción. La DB ya es Neon.
- **Cambio de contrato a tener presente**: el JSON canónico de `import-learnpack` ahora usa
  `package_format` (antes `generating_system`); la API renombró `generating_system` →
  `package_format` y `rubric_version_id` → `instrument_version_id`.
- **Rubric v1**: revisión ligera (anchors, definiciones) pendiente antes de la primera campaña
  de referencia (ADR-0015) — fuera del primer incremento del slice 2.
- **Fuera del primer incremento** (nombrado en `13-code-qa.md` §9): bucle B operativo
  (disputas/defectos), annotation queues, métricas de validez por claim, `CompareStudies`.

Fuera de alcance por decisión, no por falta de tiempo: calibración de assessors, proyecciones
CQRS, integration events salientes y el ACL de LearnPack conectado — `[futuro]`, con el diseño
del slice 2 preparando el terreno.
