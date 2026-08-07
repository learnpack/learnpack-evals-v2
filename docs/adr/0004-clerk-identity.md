# ADR-0004 — Clerk as identity provider (invite-only)

**Status:** accepted · **Date:** 2026-07 · **Context:** Identity & Access (generic)

## Context
We preferred **not to write our own auth** and to minimize login friction for SMEs (internal and
external, varied expertise). Identity is a generic subdomain; auth must come in as an
adapter behind the `IdentityPort`. Clerk and Auth0 were compared (free tiers amply
sufficient: ~50k MRU Clerk / ~25k MAU Auth0 for a handful of SMEs).

## Decision
- **Clerk (Hobby plan, free)** as the provider, for better DX with Next.js (prebuilt
  components), passwordless out of the box (email link/code) and **invite-only access** included
  in the free tier — ideal for a known roster.
- **Front (Next/Netlify):** `@clerk/nextjs` (ClerkProvider, middleware, `<SignIn/>`).
- **Back (FastAPI/Render):** dependency that validates the Clerk JWT against its **JWKS** (issuer, exp,
  signature), extracts `sub`, upserts the `Assessor` and exposes `require_admin`. A JWT template in
  Clerk shapes the claims.
- **Cross-origin:** token in `Authorization: Bearer` (no cross-site cookie); CORS restricted to the
  Netlify origin.

## Consequences
- (+) Zero auth logic of our own; polished login → less friction for SMEs.
- (+) Invite-only with no extra work; 50k MRU is more than enough.
- (−) "Secured by Clerk" badge on the free tier (cosmetic; removed on Pro).
- (−) Backend validation somewhat less "canonical OAuth2" than Auth0; resolved with a JWT
  template + standard JWKS validation.
- Since it is an adapter behind the `IdentityPort`, migrating to Auth0/another does not touch the domain.

## Alternatives
- **Auth0** → valid and more "standard OIDC"/portable; postponed due to a steeper curve for a first
  contact and invite-only requiring more configuration.
- **Own auth (magic-link/JWT in FastAPI)** → rejected: the user prefers not to write auth.
