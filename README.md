# LearnPack Evals

Sistema para **evaluar la calidad pedagógica de contenido educativo generado por IA**: un panel de
expertos puntúa cursos contra una rúbrica versionada, y el sistema agrega los juicios (promedios,
dispersión inter-rater) y establece un **golden dataset** de referencia.

- **`docs/`** — el diseño y por qué de cada límite. `docs/ARCHITECTURE.md` son las reglas duras.
- **`backend/`** — FastAPI + Postgres, hexagonal, events-first.
- **`frontend/`** — Next.js + Tailwind: flujo del evaluador y consola de admin.
- **`STATUS.md`** — en qué punto está el desarrollo hoy.

## Correrlo local, sin cuentas ni nube

Modo local: base de datos en Docker, **sin autenticación**, con usuarios y una campaña
ya cargados. Requiere Docker, [uv](https://docs.astral.sh/uv/) y Node 20+.

```bash
# 1. Base de datos
cd backend && docker compose up -d

# 2. Backend  (http://localhost:8000)
cp .env.example .env        # ya viene en modo local: nada que completar
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed        # rúbrica v1 + metadata schema
uv run python -m app.cli seed-demo   # usuarios, cursos, campaña abierta y assignments
uv run uvicorn app.main:app --reload

# 3. Frontend  (http://localhost:3000)
cd frontend
cp .env.local.example .env.local     # ya viene en NEXT_PUBLIC_AUTH_MODE=local
npm install
npm run dev
```

En `/sign-in` elegís con quién entrar:

| Usuario | Rol | Para qué |
|---|---|---|
| `admin@local.dev` | admin | cargar cursos, abrir campañas, asignar, ver reportes |
| `ada.lovelace@local.dev` | evaluator | evaluar |
| `grace.hopper@local.dev` | evaluator | evaluar (el segundo rater: sin él no hay inter-rater) |

Se cambia de usuario desde el menú del header. Para volver a empezar de cero —vacía el dataset
local y lo vuelve a sembrar—: `uv run python -m app.cli seed-demo --reset`.

### Iterar sobre la rúbrica

`docs/seed/rubric-v1.json` es la fuente de verdad. Editás, corrés `uv run python -m app.cli seed`
(actualiza en el lugar, es idempotente) y refrescás la app.

## Producción

Clerk (invite-only) + Neon + Render + Netlify. El modo local **no** aplica: `AUTH_MODE=local` con
`ENVIRONMENT=production` hace que el backend no arranque. Ver `backend/README.md`,
`frontend/README.md` y `docs/design/08-code.md` §10.
