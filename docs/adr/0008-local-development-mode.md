# ADR-0008 — Modo local: correr el sistema sin Clerk ni Neon

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** Identity & Access (genérico) + tooling

## Contexto
Hay colaboradores que trabajan **exclusivamente en rúbricas, métricas y evaluaciones**: editan
`docs/seed/rubric-v1.json`, evalúan cursos y miran los reportes. No tocan infraestructura.

Para levantar el repo hoy necesitan (a) una cuenta en Clerk con JWT template e invitación
(ADR-0004) y (b) una base en Neon (ADR-0003). Es una barrera desproporcionada para ese trabajo,
y además acopla la iteración sobre la rúbrica a dos servicios externos.

La restricción a respetar: el rol vive en `assessors.role` y **loguearse nunca cambia un rol**
(ADR-0007). Cualquier atajo de desarrollo no puede erosionar eso, ni convertirse en una forma de
entrar a un entorno real.

El corte ya existía: `tests/conftest.py::as_user` corre toda la suite —incluida la cadena de
autorización completa— sobreescribiendo **solo** `get_verified_claims`. Clerk ya estaba aislado
detrás de "dame un dict de claims".

## Decisión
**`AUTH_MODE` con dos adapters detrás de la misma dependency.** `clerk` (default) verifica el JWT
contra el JWKS; `local` construye los mismos claims a partir del header `X-Dev-User: <email>`.

Todo lo que está debajo del claim —`ResolveAssessor`, creación del assessor, `assessors.role`,
`require_admin`— es **el mismo código en los dos modos**. El modo local no bifurca reglas de
negocio: solo reemplaza de dónde sale la identidad.

Reglas duras que hacen que esto no se filtre:

| Regla | Dónde |
|---|---|
| El default del código es `clerk`; un valor que no sea `clerk`/`local` **no arranca** (en el front, que no puede fallar así, cae a `clerk`) | `Settings.auth_mode`, `lib/auth/mode.ts` |
| `AUTH_MODE=local` + `ENVIRONMENT=production` → **la app no arranca** | validador de `Settings` |
| `AUTH_MODE=local` + `DATABASE_URL` remoto → **la app no arranca** | validador de `Settings` |
| En modo `clerk` el header `X-Dev-User` **no se lee** (no es un fallback ante token ausente) | `get_verified_claims` |
| `seed-demo` y `GET /dev/identities` solo existen en modo local | `app/cli.py`, `platform/dev_router.py` |

Son **dos** condiciones para el guard y no una: `ENVIRONMENT` es una etiqueta que nada obliga a
setear —un servicio creado sin esa variable la tiene en `development`—, mientras que el host de
`DATABASE_URL` es un hecho sobre dónde viven los datos. Para servir una API sin autenticación
haría falta, además de pedir el modo explícitamente, estar apuntando a una base local.

Complementos que hacen el modo usable de verdad:
- **Base local propia** (`db-dev`, puerto 5434) separada de la de tests, porque la fixture
  `cleanup` de la suite borra filas.
- **`app.cli seed-demo`**: 3 usuarios (1 admin + 2 evaluadores), 2 cursos, 1 campaña abierta con
  quórum 2 y las 4 assignments — **todo pendiente**, sin evaluaciones precargadas. Idempotente,
  con `--reset`. Va por los use cases reales, así que publica los eventos reales. Al ser un
  seeder y no un login, **alinea el rol** de un usuario demo que ya exista: quien se logueó
  antes de sembrar nació `evaluator` y quedaría con 403 en toda la consola de admin. El
  invariante de ADR-0007 que no se toca es que *loguearse* nunca cambia un rol.
- **Selector de usuario** en `/sign-in`, alimentado por `GET /dev/identities` (la DB es la fuente
  de verdad, no una lista hardcodeada en el front). Cambiar de usuario recarga la página para
  descartar la caché de queries del anterior.

Dos evaluadores no es un capricho: con uno solo el inter-rater es `null` y nunca se dispara la
cadena `ContentEvaluationCompleted → GoldenReferenceEstablished`. El dataset mínimo para ejercitar
las métricas necesita quórum 2.

## Consecuencias
- (+) `docker compose up -d` + dos comandos y la app corre entera, sin cuentas ni nube.
- (+) El camino de producción no cambia: mismo default, mismos tests, mismo deploy.
- (+) El loop de quien trabaja en la rúbrica queda: editar el JSON → `app.cli seed` → refrescar.
- (−) Dos caminos de autenticación; el local solo se ejercita en `tests/test_auth_local.py`. Se
  mitiga manteniendo el corte finito: el modo local **solo** fabrica claims. Si algún día
  necesitara lógica propia de roles, sería la señal de que el corte se movió al lugar equivocado.
- (−) `X-Dev-User` queda en `allow_headers` de CORS también en producción. Es inerte (en modo
  `clerk` nadie lo lee) y evita mantener dos configuraciones de CORS.
- (−) El front empaqueta los dos adapters. Irrelevante en tamaño y hace que el switch sea una env
  var, no un build distinto.

## Alternativas consideradas
- **JWT local firmado con HS256** (un endpoint que emite tokens de dev) → rechazada: más fiel al
  camino real, pero agrega emisión de tokens y manejo de claves para un público que no debería
  enterarse de que existe un token. El corte quedaría en el mismo lugar igual.
- **Instancia de Clerk compartida para desarrollo** → rechazada: sigue exigiendo cuenta,
  invitación y red; no resuelve el problema, lo centraliza.
- **Autodetectar el modo local cuando faltan las claves de Clerk** → rechazada: una variable mal
  cargada en un deploy convertiría la app en un sistema sin autenticación. La activación tiene
  que ser explícita y, además, incompatible con `ENVIRONMENT=production`.
- **Un usuario único ficticio, sin selector** → rechazada: sin admin + dos evaluadores no se puede
  ejercitar ni el quórum, ni el golden, ni la dispersión inter-rater.
- **SQLite en vez de Postgres local** → rechazada: el schema usa JSONB e índices únicos parciales
  (08-code.md §3); un motor distinto en desarrollo produciría divergencias reales.

## Implementación
`AUTH_MODE` → `Settings.auth_mode` / `is_local_auth`; `platform/auth_local.py` (claims desde el
header) elegido en `platform/security.py::get_verified_claims`; `platform/dev_router.py`;
`app/cli.py seed-demo`; `docker-compose.yml` (`db-dev`). Frontend: `src/lib/auth/`
(`mode.ts` + adapters `clerk.tsx` / `local.tsx`), consumido por `layout.tsx`, `app-header.tsx`,
`sign-in`, `lib/api/hooks.ts` y `middleware.ts`.
Tests: `backend/tests/test_auth_local.py` (6 casos, incluidos el header ignorado en modo `clerk` y
el arranque prohibido en producción).
