# ADR-0004 — Clerk como proveedor de identidad (invite-only)

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** Identity & Access (genérico)

## Contexto
Se prefirió **no escribir auth propia** y minimizar la fricción de login para SMEs (internos y
externos, expertise variado). Identity es un subdominio genérico; la auth debe entrar como
adapter detrás del `IdentityPort`. Se compararon Clerk y Auth0 (free tiers ampliamente
suficientes: ~50k MRU Clerk / ~25k MAU Auth0 para un puñado de SMEs).

## Decisión
- **Clerk (plan Hobby, gratis)** como proveedor, por mejor DX con Next.js (componentes
  prearmados), passwordless de fábrica (email link/code) y **acceso solo por invitación** incluido
  en el free — ideal para un padrón conocido.
- **Front (Next/Netlify):** `@clerk/nextjs` (ClerkProvider, middleware, `<SignIn/>`).
- **Back (FastAPI/Render):** dependency que valida el JWT de Clerk contra su **JWKS** (issuer, exp,
  firma), extrae `sub`, hace upsert del `Assessor` y expone `require_admin`. Un JWT template en
  Clerk moldea los claims.
- **Cross-origin:** token en `Authorization: Bearer` (no cookie cross-site); CORS restringido al
  origin de Netlify.

## Consecuencias
- (+) Cero lógica de auth propia; login pulido → menos fricción para SMEs.
- (+) Invite-only sin trabajo extra; 50k MRU sobra.
- (−) Sello "Secured by Clerk" en el free (cosmético; se quita en Pro).
- (−) Validación en backend algo menos "OAuth2 canónica" que Auth0; se resuelve con un JWT
  template + validación JWKS estándar.
- Como es adapter detrás del `IdentityPort`, migrar a Auth0/otro no toca el dominio.

## Alternativas
- **Auth0** → válida y más "OIDC estándar"/portable; se posterga por mayor curva para un primer
  contacto e invite-only con más configuración.
- **Auth propia (magic-link/JWT en FastAPI)** → rechazada: el usuario prefiere no escribir auth.
