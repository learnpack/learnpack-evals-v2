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
                                   # viewer), assessors (with Ratify), calibration,
                                   # studies, campaigns, reports
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

## Importing courses from disk (local mode only)

`/admin/contents` shows an **Import from disk** button when the build runs with
`NEXT_PUBLIC_AUTH_MODE=local`. It opens `/admin/contents/import`, which browses the source
roots the backend declares (`LOCAL_SOURCE_ROOTS`, see `../backend/README.md`), previews what
registering each folder would do, and registers the ones you tick.

The button is behind a build-time constant, so it never reaches a deployed console — and the
endpoints it uses answer 404 outside local mode anyway. The page states that if you open it
directly.

Two things the page says that are easy to misread as bugs: a folder marked **conflict** needs
the course version bumped (a registered version is immutable, ADR-0005), and an **already
registered** course whose generator is unknown cannot be fixed by registering it again —
re-registering an unchanged package is a no-op, so the row offers the attribution act instead
(ADR-0024).

## The two acts the console performs on the automated path

Both are deliberate, irreversible and recorded with their author, so both sit behind a
dialog that states what is being committed to rather than asking whether you are sure.

**Publish an instrument version** (`/admin/instruments`) freezes it: from there any change
is a new version.

**Ratify an assessor** (`/admin/assessors`) is what lets an automated assessor's judgments
be *persisted* against one published instrument version (ADR-0019, ADR-0036). Two things
about that page read oddly until you know the domain. Ratification is per
`(assessor, instrument version)`, so a package shows a table of its lineage's versions
rather than a yes/no; and a **draft** is listed with no Ratify button, because its remedy
is publishing it, not ratifying it. When executed criteria have changed since the last
version the assessor ratified, the act comes back asking for a decision **per criterion** —
the dialog lists each one with the `pass_condition` you are confirming the executor still
realizes. That is not a formality: changing an executor is a new assessor version.

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
