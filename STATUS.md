# STATUS

**El único lugar del repo con estado fechado.** Se **reescribe** entero cuando cambia algo; no se
apila historia (para eso está git). Si encontrás estado en cualquier otro documento —"ya está
hecho", "falta X", "N tests en verde", "verificado el tal día"— está en el archivo equivocado y
va acá.

_Última actualización: 2026-07-31._

## Dónde estamos

**MVP completo y verificado en local. Falta el deploy.**

| Bloque (`docs/design/08-code.md` §12) | Estado |
|---|---|
| 1. Scaffolding + migraciones + seed | ✔ |
| 2. identity + content_registry | ✔ |
| 3. rubric_authoring + evaluation + orchestration | ✔ |
| 4. golden_dataset + reporting | ✔ |
| 5. frontend (evaluador + consola admin) | ✔ |
| Deploy (§10: Render + Netlify) | ✗ pendiente |

## Verificado

- **Suite backend en verde: 173 tests** contra Postgres local (~9 s). Requiere
  `docker compose up -d` en `backend/`; sin la DB levantada la suite da error, no skip.
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
- `docs/design/07-define.md`: diseño táctico del **modelo objetivo** en curso (el slice del MVP
  está cerrado).

Fuera de alcance por decisión, no por falta de tiempo: fuentes automáticas, `ComputedMetric`,
calibración, proyecciones CQRS y el ACL de LearnPack conectado — todo `[futuro]`.
