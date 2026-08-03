# STATUS

**El único lugar del repo con estado fechado.** Se **reescribe** entero cuando cambia algo; no se
apila historia (para eso está git). Si encontrás estado en cualquier otro documento —"ya está
hecho", "falta X", "N tests en verde", "verificado el tal día"— está en el archivo equivocado y
va acá.

_Última actualización: 2026-08-02._

## Dónde estamos

**Slice 1 (MVP humano): completo y verificado en local; falta el deploy.
Slice 2 (motor de QA de generadores): en diseño.**

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

### Slice 2 — diseño completo y promovido; falta el plan de código

El rediseño (DDD Starter Modelling Process, segunda vuelta, alcance **QA interno de
generadores**) está **cerrado y promovido a docs**:

- **`docs/design/09` … `12`** — la serie vigente (Align/Discover · Decompose/Strategize ·
  Connect · Define autocontenido). Los `01…08` quedaron como históricos con banner.
- **ADR-0009 … ADR-0015** — las decisiones (sin inferencia · criteria verificables · sin score
  único · génesis/tríada · ECD-lite/claims · vocabulario en evidence models · referencia humana
  en dos capas).
- **`docs/GLOSSARY.md`** — lenguaje del slice 2 completo + tabla de equivalencias con la
  industria de evals. **`docs/ARCHITECTURE.md`** y **`CLAUDE.md`** re-apuntados a la serie
  nueva.
- **Falta:** el plan de código del slice 2 (análogo al `08-code.md` del slice 1) y su primer
  incremento (Design con pocos claims · un adapter LearnpackV1 · Evaluation automático mínimo ·
  Studies thin).

## Verificado

- **Suite backend en verde: 179 tests** contra Postgres local (~9 s). Requiere
  `docker compose up -d` en `backend/`; sin la DB levantada la suite da error, no skip.
- **Modo local** (ADR-0008) probado de punta a punta: `seed-demo` idempotente y con `--reset`,
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
- **Sin CI** (no hay `.github/`) y sin tests de frontend. No estaba en el plan del MVP; es lo que
  falta si se quiere red de seguridad automática antes de deployar.
- **Deudas del slice 1 que se resuelven durante el desarrollo del slice 2**: Reporting aún
  publica `overall_average`/`global_average` (contra ADR-0011); se retiran con el rediseño de
  reporting. La migración de `Rubric v1` **se canceló** (ADR-0015): v1 no se migra a la forma
  ADR-0010 — se **estabiliza como instrumento de referencia** de la calibración (panel humano
  por dimensión); queda una revisión ligera (anchors, definiciones) antes de la primera campaña
  de referencia. La condición de seguridad anterior desaparece: recolectar evaluación humana
  sobre v1 es ahora su **uso previsto** — después de esa revisión.
- `docs/design/07-define.md`: diseño táctico del **modelo objetivo** en curso (el slice del MVP
  está cerrado).

Fuera de alcance por decisión, no por falta de tiempo: fuentes automáticas ejecutándose hoy,
calibración, proyecciones CQRS y el ACL de LearnPack conectado — `[futuro]`, con el diseño del
slice 2 preparando el terreno.
</content>
