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

## Clerk (ADR-0004)

El token de sesión por defecto de Clerk **no trae email ni nombre**. Hay que crear un **JWT
template** en el dashboard de Clerk con estos claims:

```json
{ "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
```

El backend tolera que falten (el perfil queda en `NULL`), pero sin ellos no vas a poder
identificar a los SMEs ni usar `set-role`.

### Roles

`assessors.role` es la **fuente de verdad** de la autorización. El primer login crea al
`Assessor` como `evaluator` y **el login nunca cambia el rol** — autenticarse no puede
escalar privilegios. La promoción es explícita:

```bash
uv run python -m app.cli set-role --email tu@email.com --role admin
```

La persona tiene que haber entrado al menos una vez para que exista su fila.

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

## Unit of work

`app/platform/uow.py` es el límite transaccional de cada use case: contiene la `Session`, el
`OutboxEventPublisher` sobre esa misma sesión y el dispatcher. `uow.commit()` commitea y
**después** despacha los eventos ya durables. Los use cases reciben `uow` + los ports que
necesitan; los adapters concretos se inyectan desde el router.

## Estado

Bloques 1 y 2 completos: scaffolding + migraciones + seed · identity (Clerk) ·
content_registry. Faltan `evaluation`, `orchestration`, `golden_dataset` y `reporting`
(bloques 3–4, `../docs/08-code.md §12`).
