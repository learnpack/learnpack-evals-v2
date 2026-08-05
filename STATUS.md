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
(`learning_objectives`, `target_audience`, `prerequisites`, `lesson_inventory`,
`lesson_bodies`, `lesson_activities`) son el contrato contra el que el adapter
`LearnpackV1` v2 declara sus capacidades. (`practice_exercises`, del borrador anterior,
quedó huérfano en la tabla `data_requirements`: el import no borra; es inofensivo.)

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
  perfila los cursos demo desde sus paquetes reales congelados — registrados con artifacts,
  así `/admin/profiles` muestra la extracción completa: inventario, cuerpos y actividades),
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
- **Enforcement de `value_domain` sobre las entries del profile: sin dueño.** Hoy la forma
  del valor de cada `data_requirement` vive solo en la prosa de su `definition`; nada valida
  una `ProfileEntry` contra un value domain. El riesgo dispara con el segundo adapter que
  cubra un mismo id con otra forma (estructural en ADR-0016: el assessor targetea
  instrumento, no formato). Decidir en el bloque 6 vía ADR: dónde se valida (candidato:
  `ContentProfile.ok()`, el chokepoint de todos los adapters) y qué vocabulario necesita
  `value_domain` — la spec mínima de 13-code §7.4 no expresa formas compuestas como las de
  `lesson_inventory` / `lesson_activities`.
- **Intake mecánico del `GenerationBrief` desde el paquete LearnpackV1: pendiente**
  (PR chico de registry, antes o durante el bloque 7 — hoy todo contenido queda con
  `brief_id = null` y no puede entrar a datasets pareados). Diseño acordado, ADR al
  implementar: el pipeline real tiene dos etapas — (prompt del usuario + material
  adjunto) → syllabus → lecciones — y el prompt original **no se persiste** (irrecuperable
  para lo ya generado). El brief se registra parcial y con su completitud declarada:
  `brief` = la description procesada de `.learn/initialSyllabus.json → courseInfo.description`
  (la instrucción operativa durante la generación de lecciones); `fields` =
  `{origin: ai_derived_syllabus, promptRecorded: false, materialsHash: <hash de
  courseInfo.contentIndex>, materialsSource: ...}` (el material vive en el paquete, no se
  duplica); identidad/dedup del brief = `hash(description + materialsHash)`. Consecuencia:
  el pareo A/B vale para "misma instrucción efectiva" (etapa de lecciones), no para
  atribuir diferencias a la formulación del prompt — `promptRecorded: false` es el dato
  con el que los studies ponen ese caveat solos. Nota para LearnPack (forward-looking):
  persistir el prompt original en el paquete (p.ej. `courseInfo.originalPrompt`) vuelve
  completos los briefs del contenido nuevo. Relacionado: el preprocesador de prompts es
  parte de la identidad del generador — versionarlo en `GeneratorVersion.metadata`.
  **Regla de disciplina (misma raíz, va al mismo ADR):** la metadata de un contenido
  registra solo lo que el paquete/plataforma **emite** (intake mecánico) — nunca
  reconstrucciones humanas ni derivaciones con IA: una declaración tipeada a mano desde
  el material del brief hace pasar criteria que miden si *el curso* declara, y enmascara
  el hallazgo real ("estaba en el brief, el generador no lo emitió"). El conocimiento
  humano sobre la intención va al brief. El schema LearnpackV1 ya no exige ningún key de
  metadata (exigirlos forzaba a tipearlos), y el seed demo registra los cursos sin
  metadata: sus profiles leen `absent`, que es el hallazgo verdadero sobre este generador.
- **Fuera del primer incremento** (nombrado en `13-code-qa.md` §9): bucle B operativo
  (disputas/defectos), annotation queues, métricas de validez por claim, `CompareStudies`.

Fuera de alcance por decisión, no por falta de tiempo: calibración de assessors, proyecciones
CQRS, integration events salientes y el ACL de LearnPack conectado — `[futuro]`, con el diseño
del slice 2 preparando el terreno.
