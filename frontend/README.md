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

The backend must be running with the matching `AUTH_MODE=local` — if the two disagree every
request is a 401 whose message says so. The list comes from
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
    admin/                         # admin console. page.tsx is the loop (versions nobody
                                   # measured + last rounds), and layout.tsx groups the
                                   # destinations by how often they are needed:
                                   #   Measure           contents, studies
                                   #   Definitions       instruments (with Publish),
                                   #                     assessors (with Ratify),
                                   #                     generators, briefs, profiles
                                   #   Human evaluation  campaigns, calibration, reports
  components/
    ui/                            # UI kit (button, card, table, dialog, select,
                                   # collapsible-section…)
    evaluator/                     # consume-content (iframe+fallback), score-form
    admin/                         # forms (content, campaign, assign), the shared badges
                                   # and palettes (study-status, outcome-badge,
                                   # claim-status), the quote/copy/distribution
                                   # primitives, and study-report/ — the report renderer
  lib/
    auth/                          # identity seam: mode.ts + clerk.tsx / local.tsx
    api/                           # client.ts (fetch+headers), types.ts, hooks.ts (TanStack)
    locator.ts                     # decodes an adapter's locator shape into a sentence
    extraction.ts                  # whether a course was read, out of profiles+capabilities
    versions.ts                    # courses grouped by the version that made them, and
                                   # which versions a round has actually measured
    constants.ts                   # rubric id, package format
  middleware.ts                    # protects everything but /sign-in (Clerk or local cookie)
```

`src/lib/api/types.ts` mirrors the FastAPI contract. Most of it is snake_case, 1:1 with the
routers' `response_model`s. The **composed-on-read projections are the exception** and are
camelCase: readiness, fitness, the criterion record and the report document are
`dict[str, Any]` on the backend with no `response_model` to mirror, so those types are the
frontend's own statement of what it expects — nothing checks them but the reader.

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

## Courses read by generator version

`/admin/contents` opens grouped by the version that made each course, because that is the
grain a round measures. A card says what that version brought — courses, commissions, how
many were read — and carries the two acts that start from there:

- **Measure this version** links to `/admin/studies/new?versions=<id>`.
- **Compare with…** offers every other version with the number of commissions **both**
  answered, zero included and in amber. It is the earliest point at which anyone can see
  that two versions are not answering the same work; the round is not refused, because a
  cross-format A/B is deliberately legitimate (ADR-0044 §7).

The link carries the versions and nothing else. The study's name and its commissions are
derived where it lands (`app/admin/studies/new/page.tsx`), so how a dataset is composed is
decided in one place rather than encoded in a query string. The commissions prefilled are the
**union** of what those versions answered — the form's own per-version counts and its unpaired
warning are what tell the reader the rest.

Two things a card says that nothing else does: courses with **no commission** can never enter
a round, and the **unknown generator** group can never be measured, since a round names the
versions it measures (ADR-0024, ADR-0044 §6). Its courses are attributed in the flat **List**
view, which also keeps the format/generator/version filters.

## Whether a course was read

`/admin/contents` carries an **Extraction** column, because a course that was never read
enters a study all the same and comes back with its criteria unassessed. Three states, and
the middle one is the one that reads oddly until you know the domain:

- **read** — a profile was recorded. Quiet, because it asks nothing of anyone.
- **not read** — no profile exists. Not a failure: automatic profiling declines when no
  adapter claims the format, when nobody has accepted that adapter's extraction yet, or when
  the package cannot be fetched over http (ADR-0029).
- **could not be read** — a profile was recorded as failed; the adapter choked on the package.

The state always comes from the profile row, never from whether the format's extraction is
accepted — `profile-content` profiles by hand regardless of acceptance, so a course in an
unaccepted format may well have been read. Acceptance only explains a *missing* profile.
`/admin/profiles` stays the place that says what to do about either exception.

## Declaring which generator version made something

Every form that asks for one — *Add course*, *Import &amp; measure*, the attribution act — asks
with the same control (`components/admin/generator-version-picker.tsx`): the lineage, then
its version, with **New** beside it. Versions change often in early development, so
registering one is done wherever it is needed rather than in a screen of its own.

The **lineage** is not creatable there: registering a generator is rare, and the refusal that
stops a typo becoming a second lineage (ADR-0031) needs the undivided attention it gets in
`/admin/generators`.

The control carries the three states of ADR-0024, and *unknown* is one of them — a
declaration, not silence — except in attribution, where naming the version is the whole act.

## Import &amp; measure (local mode only)

`/admin/measure` is one errand in three stretches, top to bottom, and it is the page the
console is arranged around:

1. **What made these courses** — the generator version, the course format, whether a person
   edited the output.
2. **Where they are** — it browses the source roots the backend declares
   (`LOCAL_SOURCE_ROOTS`, see `../backend/README.md`), previews what registering each folder
   would do, registers the ones you tick, and then says how many of the lot came back read.
3. **Measure** — `StudyForm`, the very same one `/admin/studies/new` renders, prefilled with
   the version declared in 1 and the commissions its courses brought. Composing a dataset in
   a second place would be a second set of rules to keep in step.

That third stretch reads its initial values once, at mount, so the page rebuilds it when the
declared version changes and when a batch finishes — otherwise the courses just imported
would not be ticked. A batch therefore discards anything already typed below it, which the
top-to-bottom order makes rare: you import, and then you scroll down.

The whole page is behind a build-time constant, so it never reaches a deployed console — the
scan endpoints answer 404 outside local mode anyway. There the same errand is two screens:
*Courses → Add course*, then *Studies → New study*.

Two things the page says that are easy to misread as bugs: a folder marked **conflict** needs
the course version bumped (a registered version is immutable, ADR-0005), and an **already
registered** course whose generator is unknown cannot be fixed by registering it again —
re-registering an unchanged package is a no-op, so the row offers the attribution act instead
(ADR-0024).

## The three acts the console performs on the automated path

All three are deliberate, irreversible and recorded with their author, so all three sit
behind a dialog that states what is being committed to rather than asking whether you are
sure.

**Publish an instrument version** (`/admin/instruments`) freezes it: from there any change
is a new version.

**Accept an extraction** (`/admin/profiles`) qualifies the adapter version that reads a
package format (ADR-0012): from there, registering a course in that format reads it on the
spot. It lives on that page and nowhere else, because it is judged over the profiles that
page renders — offering it where there are none would invite a judgement with nothing to
read. Two consequences worth knowing: accepting does **not** go back over courses already
registered, and reading packages by hand is how the samples that earn an acceptance are
produced, so **Read them now** comes first.

Reading is not one of the three — it writes a profile, but it decides nothing and can be
repeated. It is offered per format on `/admin/profiles`, per failed profile as **Try
again** (nothing else ever retries one: the policy stands down when a row exists, in either
state), and over a lot that came back unread on `/admin/measure`. Always as an explicit
batch, one request per course, never a cascade.

**Ratify an assessor** (`/admin/assessors`) is what lets an automated assessor's judgments
be *persisted* against one published instrument version (ADR-0019, ADR-0036). Two things
about that page read oddly until you know the domain. Ratification is per
`(assessor, instrument version)`, so a package shows a table of its lineage's versions
rather than a yes/no; and a **draft** is listed with no Ratify button, because its remedy
is publishing it, not ratifying it. When executed criteria have changed since the last
version the assessor ratified, the act comes back asking for a decision **per criterion** —
the dialog lists each one with the `pass_condition` you are confirming the executor still
realizes. That is not a formality: changing an executor is a new assessor version.

## Two happy paths

**Measuring a generator** is the automated one, and it has its own guide:
`../docs/RUNBOOK-measuring.md`. In the console it is one page — `/admin/measure` — and the result is
read on `/admin/studies/[id]`.

**Human evaluation** is the other, and it needs raters. In local mode
`task seed:demo` installs them with two courses and an open campaign to work on; with Clerk
they are invited and appear in the picker after their first sign-in.

1. Log in as **admin** → `/admin/contents`: register a course by **package URL** + generator
   + provenance — discovery reads the artifact list from the package itself (ADR-0027), so
   there is nothing to type by hand. With the extraction accepted, registering auto-profiles
   it, visible in `/admin/profiles`. A course registered from a local source declares no
   consumable URL (ADR-0028): it shows as *not deployed* and cannot be assigned for human
   scoring, so use a real deployed course for this walkthrough.
2. `/admin/campaigns`: new campaign (quorum, courses).
3. Assign the course to two evaluators in `/admin/campaigns/[id]`.
4. Log in as an evaluator → `/evaluations` → 3-step wizard → submit.
5. Back to admin → progress `1/1` + golden `usable` in the campaign detail; scores and
   inter-rater in `/admin/reports`.
