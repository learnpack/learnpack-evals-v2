# backend

FastAPI + Postgres (Neon). Diseño en `../docs/` — **es la fuente de verdad**.
Reglas duras: `../docs/ARCHITECTURE.md`. Nombres: `../docs/GLOSSARY.md`.

## Setup

```bash
cp .env.example .env      # completar DATABASE_URL (Neon) y las claves de Clerk
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed          # rubric v1 + metadata schema (idempotente)
uv run uvicorn app.main:app --reload
```

`GET /health` verifica que la API arranca y que la DB responde.

## Capas (Dependency Rule)

| Carpeta | Capa | Puede importar |
|---|---|---|
| `app/modules/*/domain` | Domain | nada de framework — **Python puro** |
| `app/modules/*/application` | Application | su propio domain + `shared`; **define los ports** |
| `app/modules/*/infrastructure` | Adapters | application + domain (repos, routers, ACLs) |
| `app/platform`, `app/main.py` | Frameworks | todo; inyecta las dependencias |

Ningún módulo importa el dominio interno de otro: se hablan por **domain events**
(`app/platform/events.py`) y por **DTOs de query** de solo lectura.

## Events-first (ADR-0003)

Publicar un evento = `INSERT` en `events` con la sesión del use case, dentro de la misma
transacción que el agregado (`OutboxEventPublisher`). Tras el commit, el `EventDispatcher`
in-process entrega el evento a las policies suscritas. Los handlers deben ser idempotentes
por `event_type + aggregate_id`, para poder reprocesar desde la tabla `events`.

## Comandos

```bash
uv run pytest            # tests (los que necesitan DB se saltean sin DATABASE_URL)
uv run ruff check .      # lint
uv run ruff format .     # formato
```

## Estado

Bloque 1 (scaffolding + migraciones + seed) completo. `app/modules/*` están vacíos a
propósito: se llenan en los bloques 2–4 según `../docs/08-code.md §12`.
