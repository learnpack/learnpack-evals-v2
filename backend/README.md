# backend

FastAPI + Postgres (Neon). Diseño en `../docs/` — **es la fuente de verdad**.
Reglas duras: `../docs/ARCHITECTURE.md`. Nombres: `../docs/GLOSSARY.md`.
En qué punto está el desarrollo hoy: `../STATUS.md` (este README describe **cómo funciona**, no
en qué estado está).

## Setup

```bash
cp .env.example .env      # completar DATABASE_URL (Neon) y las claves de Clerk
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed          # rubric v1 + metadata schema (idempotente)
uv run uvicorn app.main:app --reload
```

`GET /health` verifica que la API arranca y que la DB responde.

## Modo local: sin Clerk y sin Neon (ADR-0008)

`AUTH_MODE` decide de dónde sale la identidad de un request:

| Modo | Identidad | Cuándo |
|---|---|---|
| `clerk` (default) | JWT de sesión verificado contra el JWKS | producción y cualquier entorno real |
| `local` | el header `X-Dev-User: <email>`, sin verificar | desarrollo, sin cuentas ni nube |

Debajo del claim **es el mismo código en los dos modos**: `ResolveAssessor`, `assessors.role`,
`require_admin`. El modo local no bifurca reglas de negocio, solo reemplaza de dónde sale la
identidad — el mismo corte que usa la suite de tests.

```bash
docker compose up -d                       # levanta db (5433, tests) y db-dev (5434, desarrollo)
cp .env.example .env                       # el ejemplo ya viene en modo local
uv run alembic upgrade head
uv run python -m app.cli seed
uv run python -m app.cli seed-demo         # --reset para empezar de cero
```

`--reset` **vacía el dataset local** (cursos, campañas, evaluaciones y usuarios `local|`) y
vuelve a sembrar; no toca la rúbrica ni los metadata schemas. Es a propósito más amplio que
"borrar lo que la lista dice hoy": editar `DEMO_ASSESSORS`/`DEMO_CONTENTS` es la forma normal de
armar un demo, y un borrado acotado deja huérfano todo lo que creó la versión anterior —un
usuario renombrado sigue apareciendo en el selector, un curso reemplazado queda sin campaña— sin
forma de limpiarlo. Solo puede correr contra una base local, así que no hay nada que perder.

`seed-demo` deja 3 usuarios (`admin@local.dev`, `ada.lovelace@local.dev`,
`grace.hopper@local.dev`), 2 cursos y una campaña abierta con **quórum 2** y sus 4 assignments,
todo **pendiente de evaluar**. Dos evaluadores es el mínimo para que haya dispersión inter-rater
y para que se dispare `ContentEvaluationCompleted → GoldenReferenceEstablished`.

Va por los use cases reales, así que publica los mismos eventos que produciría la UI. Es
idempotente: correrlo dos veces no duplica nada.

Lo que impide que esto se filtre a un entorno real:

- El default del código es `clerk` (el `.env.example` trae `local` porque es la plantilla de
  desarrollo; en producción las variables las pone Render). Un valor que no sea `clerk` ni
  `local` **no arranca**: es un error de configuración, no algo que se degrade en silencio.
- `AUTH_MODE=local` con `ENVIRONMENT=production` → **la app no arranca**.
- `AUTH_MODE=local` con un `DATABASE_URL` que no apunte a localhost → **tampoco arranca**.
  Son dos chequeos porque cada uno cubre el punto ciego del otro: `ENVIRONMENT` es una etiqueta
  que nadie garantiza (puede estar sin setear en el server), mientras que el host de la base es
  un hecho sobre dónde viven los datos.
- En modo `clerk` el header `X-Dev-User` **no se lee**: no es un fallback cuando falta el token,
  es otro adapter.
- `seed-demo` aborta si el modo no es `local` (no puede escribir datos demo en Neon por error).
- `GET /dev/identities` —la lista que alimenta el selector de usuario del front— da 404 fuera del
  modo local.

## Clerk (ADR-0004)

El token de sesión por defecto de Clerk **no trae email ni nombre**. Hay que crear un **JWT
template** en el dashboard de Clerk con estos claims:

```json
{ "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
```

El backend tolera que falten (el perfil queda en `NULL`), pero sin ellos no vas a poder
identificar a los SMEs ni usar `set-role`.

**Creá el template antes de que entre nadie.** El claim `email` es además lo que decide el rol
inicial del primer admin, y esa decisión se toma **una sola vez** — ver el orden en
[Preparar un entorno](#preparar-un-entorno--el-orden-importa).

### Roles y el primer admin (ADR-0007)

`assessors.role` es la **fuente de verdad** de la autorización, y **el login nunca cambia el
rol de nadie** — autenticarse no puede escalar privilegios.

Para el arranque (hace falta un admin antes de que exista un admin que pueda crearlo), está
`ADMIN_EMAILS`: una allowlist de **aprovisionamiento**, no de autorización. Solo decide el rol
**con el que se crea** un assessor nuevo:

```bash
ADMIN_EMAILS=vos@tuempresa.com,otro@tuempresa.com
```

- Email en la lista y la persona **nunca entró** → se crea `admin`.
- Email en la lista pero la persona **ya existe** como `evaluator` → **sigue** `evaluator`.
- Un `admin` existente al que **sacás** de la lista → **sigue** `admin`.
- Sin claim `email` (falta el JWT template) → `evaluator`.

Es seguro **porque el acceso es invite-only**: nadie puede registrarse con el email de un admin
sin la invitación. Si alguna vez desactivás invite-only, revisá ADR-0007.

Para cambiar el rol de alguien que ya existe, el único camino es:

```bash
uv run python -m app.cli set-role --email tu@email.com --role admin
```

### Preparar un entorno — **el orden importa**

Esta secuencia se corre **una vez por entorno** (una instancia de Clerk = un entorno), antes de
que entre nadie.

> ⚠️ **El JWT template con el claim `email` tiene que existir ANTES del primer login del
> admin.** Sin ese claim el assessor se crea como `evaluator` (degrade seguro), y como la
> allowlist se aplica **una sola vez, al crear la fila**, agregar el template después ya no lo
> rescata. Dos comportamientos correctos por separado que, en el orden equivocado, dejan al
> admin nacido evaluador.

1. **Render:** `ADMIN_EMAILS=<email del admin>` (y esperá a que termine el redeploy).
2. **Clerk:** creá el **JWT template** con el claim `email` (ver arriba) e invitá las dos
   cuentas. Todavía **nadie entra**.
3. **Recién ahora:** que entre el admin. Verificá con `GET /me` que dice `"role": "admin"`.
4. Que entre el evaluador → queda `evaluator`.
5. Cargá los cursos (`import-learnpack`) y abrí la campaña desde la UI de admin.

**Si te equivocaste de orden** (el admin ya entró y quedó `evaluator`): no hay que borrar nada
ni tocar la allowlist, se arregla con

```bash
uv run python -m app.cli set-role --email <email del admin> --role admin
```

que es el único mecanismo para cambiar el rol de alguien que ya existe.

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
docker compose up -d     # Postgres local: db (tests) + db-dev (desarrollo)
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # formato
uv run mypy              # tipos (estricto, scope en pyproject.toml)
```

Todo esto corre también en CI en cada PR y push a main (`.github/workflows/ci.yml`): lint +
formato + tipos + suite backend (con Postgres como service container) + typecheck del frontend
(`npm run typecheck`).

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

La cadena completa del MVP, toda por eventos (`../docs/design/08-code.md` §5):

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

## Módulos

scaffolding + seed · identity · content_registry · rubric_authoring (read-only) · evaluation ·
orchestration · golden_dataset · reporting. Cada uno con `domain/`, `application/` e
`infrastructure/`, y su contrato en `public.py`.

El plan que los originó está congelado en `../docs/design/08-code.md`; el estado de avance, en
`../STATUS.md`.
