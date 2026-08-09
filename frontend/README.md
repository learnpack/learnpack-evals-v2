# frontend

Next.js (App Router) + TypeScript + Tailwind + Clerk. Consumes the FastAPI in `../backend`.
Design lives in `../docs/` — **it is the source of truth**. Where development stands today:
`../STATUS.md` (this README describes **how it works**, not what state it is in).

## Stack

- **Next.js 15** (App Router, `src/`) + **React 19** + **TypeScript**.
- **Tailwind** with an in-house shadcn-style UI kit in `src/components/ui/` (no Radix).
- **Clerk** (`@clerk/nextjs`) for identity, invite-only — or **local mode without identity**
  (ADR-0008), behind the same seam.
- **TanStack Query** for data-fetching/server state.
- **react-hook-form + zod** in the scoring form.

## Setup

```bash
cp .env.local.example .env.local     # ships in local mode: nothing to fill in
npm install
npm run dev                          # http://localhost:3000
```

To use Clerk instead, remove `NEXT_PUBLIC_AUTH_MODE=local` and fill in the keys (below).

The backend must be running (`../backend`, `:8000` by default) with `ALLOWED_ORIGINS`
including `http://localhost:3000`.

## Local mode: no Clerk (ADR-0008)

With `NEXT_PUBLIC_AUTH_MODE=local` (what `.env.local.example` ships) the app does not use
Clerk: `/sign-in` shows the list of local users and you pick one. Switch users from the
header menu — it reloads the page on purpose, so the previous user's query cache does not
survive on screen.

The backend must be running with the matching `AUTH_MODE=local`: the list comes from
`GET /dev/identities`, which only exists in that mode, and calls identify themselves with
the `X-Dev-User` header instead of `Authorization: Bearer`.

Any other value — or none — uses Clerk. The seam is in `src/lib/auth/`: `mode.ts` decides
and the `clerk.tsx` / `local.tsx` adapters expose the same interface (`AuthProvider`,
`useAuthHeaders`, `UserMenu`, `SignInScreen`). **No component imports `@clerk/nextjs`
directly**; everything goes through `@/lib/auth`, so switching modes touches no feature
code.

## Clerk (ADR-0004) — read before the first login

This configuration happens **once per environment** (one Clerk instance = one environment),
before the first login.

Clerk's **default session token carries neither `email` nor `name`**, and the backend needs
them to populate the `Assessor` and decide the first admin's role (`ADMIN_EMAILS`,
ADR-0007). Therefore:

1. In the Clerk dashboard create a **JWT template** (e.g. `learnpack-evals`) with:
   ```json
   { "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
   ```
2. Put that name in `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`. The frontend requests the token with
   `getToken({ template })` (see `src/lib/api/hooks.ts`).
3. **The template must exist BEFORE the admin's first login** — otherwise they are born
   `evaluator` and the allowlist does not rescue them (see `../backend/README.md`).

Access is **invite-only**: configured in Clerk (Restrictions → Allowlist / invitations).
Evaluators appear in the assignment picker **after their first sign-in**.

## Structure

```
src/
  app/
    page.tsx                       # redirects by role (admin → /admin, else → /evaluations)
    sign-in/[[...sign-in]]/        # <SignInScreen/> of the active adapter
    evaluations/                   # evaluator flow (list + 3-step wizard)
    admin/                         # admin console: contents, generators, briefs,
                                   # instruments (with Publish), profiles (extraction
                                   # viewer), campaigns, reports
  components/
    ui/                            # UI kit (button, card, table, dialog, select…)
    evaluator/                     # consume-content (iframe+fallback), score-form
    admin/                         # content-form, campaign-form, assign-form
  lib/
    auth/                          # identity seam: mode.ts + clerk.tsx / local.tsx
    api/                           # client.ts (fetch+headers), types.ts, hooks.ts (TanStack)
    constants.ts                   # rubric id, package format
  middleware.ts                    # protects everything but /sign-in (Clerk or local cookie)
```

`src/lib/api/types.ts` is the TypeScript mirror of the FastAPI contract (snake_case, 1:1
with the routers' `response_model`s).

## Content iframe

LearnPack courses **allow embedding**, so the evaluator consumes the content without
leaving the app. But embedding depends on the site serving each course —
`X-Frame-Options`/CSP `frame-ancestors` block it silently and the iframe just stays
blank — so step 2 (`components/evaluator/consume-content.tsx`) always has a net: it tries
the iframe and, if no load is reported within ~3.5 s, shows a "cannot embed" notice; the
**"Open in a new tab"** button is always visible. If a course served from another domain
shows up, check that it still works.

## Deploy (Netlify)

- Base dir `frontend` (see `netlify.toml`, plugin `@netlify/plugin-nextjs`).
- Env: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_API_URL`,
  `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`.
- Add the Netlify origin to `ALLOWED_ORIGINS` in the backend.

## Demo happy path

1. Log in as **admin** → `/admin/contents`: register a course by **package URL** + generator
   + provenance — discovery reads the artifact list from the package itself (ADR-0027), so
   there is nothing to type by hand. With the extraction accepted, registering auto-profiles
   it, visible in `/admin/profiles`. A course registered from a local source declares no
   consumable URL (ADR-0028): it shows as *not deployed* and cannot be assigned for human
   scoring, so use a real deployed course for this walkthrough.
2. `/admin/campaigns`: new campaign (quorum, courses).
3. Invite/log in an **evaluator** in Clerk → appears in the picker → assign them the course
   in `/admin/campaigns/[id]`.
4. Log in as the evaluator → `/evaluations` → 3-step wizard → submit.
5. Back to admin → progress `1/1` + golden `usable` in the campaign detail; scores and
   inter-rater in `/admin/reports`.
