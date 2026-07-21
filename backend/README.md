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

## Superficie pública de un módulo (ARCHITECTURE.md §3)

Cada módulo expone su contrato en `modules/<m>/public.py`: DTOs de query, nombres de sus
eventos, y un proveedor `get_<m>_queries` para inyectar por `Depends` que **arma su propio
repo adentro**. Los módulos ajenos importan **solo** de ahí — nunca de
`modules/<otro>/infrastructure` (eso los acoplaría al adapter concreto en vez de al port) ni
de `modules/<otro>/domain`.

Única excepción: el composition root (`main.py`, `cli.py`, `platform/`), cuyo trabajo *es*
inyectar adapters concretos.

`tests/test_architecture.py` hace la regla ejecutable: falla el build si alguien la rompe.
Corre en cada `pytest`, sin DB.

## Events-first (ADR-0003)

Publicar un evento = `INSERT` en `events` con la sesión del use case, dentro de la misma
transacción que el agregado (`OutboxEventPublisher`). Tras el commit, el `EventDispatcher`
in-process entrega el evento a las policies suscritas. Los handlers deben ser idempotentes
por `event_type + aggregate_id`, para poder reprocesar desde la tabla `events`.

## Comandos

```bash
docker compose up -d     # Postgres local para los tests (una sola vez)
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # formato
```

### Por qué los tests corren contra Postgres local

La suite está **limitada por latencia**, no por CPU: cada consulta a Neon (`us-east-1`) cuesta
~150 ms desde Latam, y un test de integración hace más de cien. Eso son ~20 s por test
y +10 min de suite. Contra Postgres local la misma consulta cuesta ~0,3 ms.

Con `TEST_DATABASE_URL` seteada (ver `.env.example`), `tests/conftest.py` redirige la suite a
esa DB y la **migra y siembra sola**. Sin ella, los tests corren contra `DATABASE_URL` — es
válido, solo lento; en ese caso conftest **no** migra ni siembra nada (no se toca el store real
automáticamente).

Neon sigue siendo el store de verdad: migraciones, deploy y la verificación de humo final.

## Unit of work

`app/platform/uow.py` es el límite transaccional de cada use case: contiene la `Session`, el
`OutboxEventPublisher` sobre esa misma sesión y el dispatcher. `uow.commit()` commitea y
**después** despacha los eventos ya durables. Los use cases reciben `uow` + los ports que
necesitan; los adapters concretos se inyectan desde el router.

## Policy de completitud (ADR-0002)

Única policy del MVP. Al oír `EvaluationSubmitted`, `orchestration` marca `submitted` todas
las assignments abiertas de `(assessor, content)` cuya campaña use la misma `rubricVersion`
—así una evaluación puede satisfacer varias campañas— y publica
`ContentEvaluationCompleted` cuando `COUNT(assignments submitted) ≥ required`.

Corre **después** del commit de la evaluación, en su propia transacción: la completitud es
**eventual**, no un invariante transaccional. Es idempotente (`ON CONFLICT DO NOTHING` +
publicar solo si insertó), así que reprocesar desde `events` es seguro.

## Golden Dataset y reportes (bloque 4)

La cadena completa del MVP, toda por eventos (08-code.md §5):

```
EvaluationSubmitted → (orchestration) ContentEvaluationCompleted
                    → (golden)        GoldenReferenceEstablished
```

Golden no lleva su propio conteo: le pide la cobertura a orchestration por su query port y
aplica su regla (`coverage ≥ threshold`). Es idempotente igual que la de quórum.

**Reporting** (ADR-0006) compone los demás módulos por sus `public.py` y agrega en Python —
sin JOINs cross-módulo y sin tablas de read model. Endpoints: `GET /admin/reports/scores`
(scores por curso, promedios por evaluador y global, dispersión inter-rater) y
`GET /admin/progress` (quién evaluó qué, cross-campaña).

Dos reglas de agregación que conviene no confundir:
- Una **repetición** es el mismo assessor sobre el mismo `(content, rubricVersion)` — se
  colapsa a la más reciente, porque es una corrección. Evaluar **dos cursos distintos** no es
  una repetición.
- La dispersión con un solo rater es `null`, no `0`: no hay acuerdo que medir.

## Carga masiva de cursos

```bash
uv run python -m app.cli import-learnpack --file cursos.json        # forma canónica
uv run python -m app.cli import-learnpack --file cursos.json --acl  # forma cruda de LearnPack
```

## Estado

**Backend completo** (bloques 1–4): scaffolding + seed · identity · content_registry ·
rubric_authoring (read-only) · evaluation · orchestration · golden_dataset · reporting.
Falta el frontend (bloque 5) — ver `../docs/08-code.md §12`.
