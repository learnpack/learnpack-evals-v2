# frontend

Next.js (App Router) + TypeScript + Tailwind + Clerk. Consume el FastAPI del `../backend`.
Diseño en `../docs/` — **es la fuente de verdad** (bloque 5 de `../docs/design/08-code.md`).
En qué punto está el desarrollo hoy: `../STATUS.md` (este README describe **cómo funciona**, no
en qué estado está).

## Stack

- **Next.js 15** (App Router, `src/`) + **React 19** + **TypeScript**.
- **Tailwind** con un kit de UI propio estilo shadcn en `src/components/ui/` (sin Radix).
- **Clerk** (`@clerk/nextjs`) para identidad, invite-only — o **modo local sin identidad**
  (ADR-0008), detrás del mismo seam.
- **TanStack Query** para data-fetching/estado del servidor.
- **react-hook-form + zod** en el formulario de scoring.

## Setup

```bash
cp .env.local.example .env.local     # viene en modo local: nada que completar
npm install
npm run dev                          # http://localhost:3000
```

Para usar Clerk en su lugar, sacá `NEXT_PUBLIC_AUTH_MODE=local` y completá las claves (abajo).

El backend tiene que estar corriendo (`../backend`, por defecto en `:8000`) y su
`ALLOWED_ORIGINS` tiene que incluir `http://localhost:3000`.

## Modo local: sin Clerk (ADR-0008)

Con `NEXT_PUBLIC_AUTH_MODE=local` (lo que trae `.env.local.example`) la app no usa Clerk:
`/sign-in` muestra la lista de usuarios locales y elegís con cuál entrar. Se cambia de usuario
desde el menú del header — recarga la página a propósito, para que no sobreviva en pantalla la
caché de queries del usuario anterior.

El backend tiene que estar corriendo con el `AUTH_MODE=local` correspondiente: la lista sale de
`GET /dev/identities`, que solo existe en ese modo, y las llamadas se identifican con el header
`X-Dev-User` en lugar del `Authorization: Bearer`.

Cualquier otro valor —o ninguno— usa Clerk. El seam está en `src/lib/auth/`: `mode.ts` decide y
los adapters `clerk.tsx` / `local.tsx` exponen la misma interfaz (`AuthProvider`,
`useAuthHeaders`, `UserMenu`, `SignInScreen`). **Ningún componente importa `@clerk/nextjs`
directamente**; todos pasan por `@/lib/auth`, así que cambiar de modo no toca código de feature.

## Clerk (ADR-0004) — leer antes del primer login

Esta configuración se hace **una vez por entorno** (una instancia de Clerk = un entorno), antes
del primer login.

El token de sesión **por defecto de Clerk no trae `email` ni `name`**, y el backend los
necesita para poblar el `Assessor` y decidir el rol del primer admin (`ADMIN_EMAILS`,
ADR-0007). Por eso:

1. En el dashboard de Clerk creá un **JWT template** (p.ej. `learnpack-evals`) con:
   ```json
   { "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
   ```
2. Poné ese nombre en `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`. El front pide el token con
   `getToken({ template })` (ver `src/lib/api/hooks.ts`).
3. **El template tiene que existir ANTES del primer login del admin** — si no, nace
   `evaluator` y la allowlist no lo rescata (ver `../backend/README.md`).

Acceso **invite-only**: se configura en Clerk (Restrictions → Allowlist / invitations). Los
evaluadores aparecen en el selector de asignación **después de su primer sign-in**.

## Estructura

```
src/
  app/
    page.tsx                       # redirige según rol (admin → /admin, si no → /evaluations)
    sign-in/[[...sign-in]]/        # <SignInScreen/> del adapter activo
    evaluations/                   # flujo del evaluador (lista + wizard 3 pasos)
    admin/                         # consola admin (courses, campaigns, reports)
  components/
    ui/                            # kit de UI (button, card, table, dialog, select…)
    evaluator/                     # consume-content (iframe+fallback), score-form
    admin/                         # content-form, campaign-form, assign-form
  lib/
    auth/                          # seam de identidad: mode.ts + clerk.tsx / local.tsx
    api/                           # client.ts (fetch+headers), types.ts, hooks.ts (TanStack)
    constants.ts                   # rubric id, LearnpackV1 metadata keys
  middleware.ts                    # protege todo salvo /sign-in (Clerk o cookie local)
```

`src/lib/api/types.ts` es el espejo TypeScript del contrato de FastAPI (snake_case, 1:1 con
los `response_model` de los routers).

## iframe del contenido (§8)

Los cursos de LearnPack **se dejan embeber**, así que el evaluador consume el contenido sin salir
de la app. Pero el embed depende del sitio que sirve cada curso —`X-Frame-Options`/CSP
`frame-ancestors` lo bloquean sin avisar y el iframe simplemente queda en blanco—, por eso el
paso 2 (`components/evaluator/consume-content.tsx`) siempre tiene red: intenta el iframe y, si no
reporta carga en ~3.5 s, muestra un aviso de "no se puede embeber"; el botón **"Abrir en pestaña
nueva"** está visible siempre. Si aparece un curso servido desde otro dominio, chequear que siga
funcionando.

## Deploy (Netlify, §10)

- Base dir `frontend` (ver `netlify.toml`, plugin `@netlify/plugin-nextjs`).
- Env: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_API_URL`,
  `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`.
- Sumá el origin de Netlify a `ALLOWED_ORIGINS` en el backend.

## Happy-path del demo

1. Login como **admin** → `/admin/contents`: alta de un curso (con una `consumable_url` real).
2. `/admin/campaigns`: nueva campaña (quórum, cursos, `metadata_view`).
3. Invitá/logueá un **evaluador** en Clerk → aparece en el selector → asignale el curso en
   `/admin/campaigns/[id]`.
4. Login como evaluador → `/evaluations` → wizard de 3 pasos → submit.
5. Volvé a admin → progreso `1/1` + golden `usable` en el detalle de campaña; scores e
   inter-rater en `/admin/reports`.
