# Deploying an instance

One errand: **a human evaluation campaign**, where subject-matter experts who do not have this
repository open a course in a browser and score it. That needs real accounts and somewhere to
keep what they answer — so it needs Clerk, a store and two hosts.

**Follow this top to bottom, once per instance.** The order is not a preference: three of the
steps degrade *silently* if they run late, and one of them stops being repairable the moment an
expert answers.

Measuring a generator's output needs none of it — that runs on your machine in
[local mode](README.md#local-mode-and-clerk-mode-adr-0008).

## Before you start

All of this lives outside the repository:

| | |
|---|---|
| **Neon** | a project, in the region the API will run in |
| **Render** | an account on a **paid** instance type: the pre-deploy command that runs the migrations does not exist on free |
| **Netlify** | an account, and its CLI (`npm i -g netlify-cli`, then `netlify login`) |
| **A domain you can add DNS records to** | Clerk's production instance requires one. Without it you are on a development instance — 100 users, emails prefixed `development`, and the session carried in the querystring instead of a cookie |
| **A GitHub account to publish the image from** | Any account; it needs no relation to this repository. Two **classic** tokens — `write:packages` for you, `read:packages` for Render (step 1) |
| **The courses, deployed** | An expert opens them in a browser, so each one needs a URL (ADR-0028) |
| **The first admin's email address** | |

Every command below runs from `backend/` **on your own machine**, never from a shell on the
server: the image is built from `backend/` alone, so the seeder's own files are not in it.

> **Rehearse first if you can.** The identity half — the JWT template, the first admin, an
> invitation redeemed — is the part whose order cannot be repeated, and all of it can be
> exercised against `localhost` before any of this exists. See
> [Rehearsing Clerk against your own machine](#rehearsing-clerk-against-your-own-machine).

---

## 1. Publish the API image

Render does not build this repository; it runs a **prebuilt image**, and one has to exist before
a service can point at it.

**Nothing is created by hand**: the first push creates the package. Log in with a **classic**
personal access token scoped `write:packages` as the password — GHCR refuses fine-grained ones
— and publish:

```bash
docker login ghcr.io -u <your github user>
cp .env.instance.example .env.instance      # IMAGE_REPO is the only one needed for now
task deploy:api
```

`.env.instance.example` says what to write in `IMAGE_REPO` and what it has to satisfy. The rest
of that file is filled in at step 7.

`deploy:api` refuses while anything tracked is uncommitted — it tags the image with the commit,
and a tag that misdescribes its contents outlives the chance to notice.

Afterwards, **check in GitHub that the package is private**. Storage and bandwidth for the
container registry are free today, so the image's size does not matter.

## 2. The store (Neon)

Create the project. Three of its options matter:

| | |
|---|---|
| **Postgres version** | **17** — what the test suite and the local container run, so it is the version everything here is tested against |
| **Region** | **You choose it here**, and Render's service goes in the same one at step 3. Neon names regions after AWS and Render after cities: Virginia is `us-east-1`, Ohio `us-east-2`, Oregon `us-west-2`, Frankfurt `eu-central-1`, Singapore `ap-southeast-1` |
| **Enable Neon Auth** | **Leave it off.** Identity here is Clerk's job, and this would add tables of its own to the database for nothing |

One region for both because **the API queries the database many times per request**, so that
distance is paid over and over. The distance to whoever is browsing is paid once, and barely
shows.

Then keep the connection string. Nothing is run with it here: it is a value you paste twice,
into Render's environment at step 3 and into `backend/.env.instance` at step 7. **Neon hands
you a `postgresql://…` string, and it needs one edit** — the driver prefix, keeping the SSL
that is already there:

```text
DATABASE_URL=postgresql+psycopg://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Nothing migrates it by hand. The API's pre-deploy command is `alembic upgrade head`, so the
first release is also the first migration.

## 3. The API (Render)

A web service of type **Existing image**:

| Field | Value |
|---|---|
| Image URL | your `IMAGE_REPO:latest` |
| Credential | the `read:packages` token |
| Region | the one Neon is in |
| Instance type | any **paid** one |
| Health check path | `/health` |
| Pre-deploy command | `alembic upgrade head` |

And its environment:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `AUTH_MODE` | `clerk`. Declared rather than left to the default, so a refusal is never what discovers it: `local` here does not boot at all (ADR-0008) |
| `DATABASE_URL` | Neon, from step 2 |
| `CLERK_ISSUER` | step 5 |
| `CLERK_SECRET_KEY` | step 5. Without it an invitation is recorded here and never created in Clerk, so the person invited cannot sign in at all (ADR-0049) |
| `ADMIN_EMAILS` | the first admin. Provisioning, not authorization: it decides the role a **new** assessor is created with and never changes an existing one (ADR-0007) |
| `ALLOWED_ORIGINS` | step 4, and that entry goes **first** |

Two of those cannot be known yet — the Clerk keys and the console's origin — so a first pass
with placeholders and one edit afterwards is the normal shape of this step.

**What is deliberately absent:** `CLERK_JWKS_URL` (empty, it is derived from the issuer; a
value copied from a local `.env` silently wins and points this instance at a development one) ·
`LLM_API_KEY` (no assessor judges from here) · `BREATHECODE_*` and `RIGOBOT_*` (ADR-0061's
seats are optional: unset, the course loads without its AI and says so) · `LOCAL_SOURCE_ROOTS`
(local trees are served only under `AUTH_MODE=local`).

`GET /health` answering `{"status": "ok", "environment": "production"}` is what says the schema
and the store are both there — it runs a real query, so it cannot answer `ok` over a database
it cannot reach.

## 4. The console (Netlify), and the domain

Netlify does not build this repository either, so the site is created and published from here.
`netlify.toml` at the repository root declares the base directory, the build and the Node
version, and the CLI reads it exactly as a hosted build would.

```bash
netlify sites:create --name <the site>
netlify link
```

**Then the domain**, added to this site — `evals.yourdomain.com` — because Clerk's production
instance needs its records on the same one (step 5). The **API stays on `onrender.com`**: its
token travels in the `Authorization` header and the backend runs `allow_credentials=False`, so
it is cross-origin by design.

Set the environment in the Netlify dashboard. **All of it is read at build time**, so changing
any of it needs a new release rather than a restart:

```text
NEXT_PUBLIC_API_URL=https://<the render service>.onrender.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/accept-invitation
```

`NEXT_PUBLIC_AUTH_MODE` is left unset on purpose: anything that is not `local` is `clerk`, so a
missing or misspelled value fails safe.

Publish it with `task deploy:console` (`task deploy:console:preview` publishes to a draft URL
instead, to look at before promoting).

> ⚠️ Now set `ALLOWED_ORIGINS` on Render to **the custom domain**, first in the list. That
> first entry is both what CORS allows and where Clerk's invitation link lands
> (`Settings.invitation_redirect_url`) — and an invitation that arrives at the wrong origin is
> found by the one person who cannot accept it.

## 5. Clerk — all of it before anybody signs in

1. **Create the production instance** and add the DNS records it asks for, on the domain from
   step 4. Its Frontend API lives at `clerk.<your domain>` for a reason: if it and the console
   were not same-site, the session cookie would need `SameSite=None`, which Safari does not
   accept.
2. **Write the JWT template**, with `CLERK_SECRET_KEY` in your shell:

   ```bash
   uv run python -m app.cli setup-clerk-jwt-template
   ```

   Idempotent, and it says which of three things it did. What it writes and why is
   [in the reference](#the-jwt-template-in-detail).
3. **Invite-only**, under Restrictions.
4. **Invite the admin's account** — and add the data-use notice to Clerk's invitation email
   template while you are there ([Inviting evaluators](#inviting-evaluators-adr-0049)).

> ⚠️ **The template must exist before the admin's first login.** Without the `email` claim the
> assessor is created as an `evaluator` — a safe degrade — and `ADMIN_EMAILS` applies once, at
> row creation, so writing the template afterwards rescues nobody.

**Nobody signs in yet.**

## 6. The first admin signs in

Now, and not before. Verify with `GET /me` that it says `"role": "admin"`.

Everything below is attributed to somebody, so this row has to exist first: an act names its
author (ADR-0042), and `--email` is how it finds them.

**If the order went wrong** and they landed as an `evaluator`, there is nothing to delete and
no allowlist to touch:

```bash
uv run python -m app.cli set-role --email <admin email> --role admin
```

That is the break-glass path — at this point there is no admin, so nobody could grant the role
from the console.

## 7. What the store has to hold

**Fill in the rest of `backend/.env.instance` now** — the store, the admin, the generator and
the courses; its `.example` says what each one is for. It is what points these tasks at the
deployed store, and values from it win over `backend/.env`, so your local environment is left
alone.

Each task prints the host it is about to write to and refuses until `CONFIRM` names it back —
they live in the same file as `db:reset`, and the two must never be confused.

```bash
CONFIRM=<the neon host> task instance:seed        # re-runnable
CONFIRM=<the neon host> task instance:generator   # once, ever
```

`instance:seed` installs the two things nothing in the app can author — the **human reference
instrument** (one Likert statement per quality, ADR-0052) and the **pedagogical reference
data** — and then **accepts the extraction** for both package formats. `instance:generator` is
separate because it is the one act here that must not be idempotent: a lineage takes a typed
name, so a second one is a typo worth refusing (ADR-0031).

> ⚠️ **Accepting the extraction is the step that is paid for in data.** It arms automatic
> profiling on registration (ADR-0029), and an item is withheld from a human only where a
> profile *settles* that its datum is undeclared (ADR-0053). A course with no profile settles
> nothing — so the four items a `LearnpackV1` course cannot answer get **asked anyway**, of
> every expert, with no error and no log. Accepting it *before* the courses are registered is
> what makes profiling automatic; accepting it afterwards profiles nothing retroactively, and
> those courses stay unread until somebody reads them from `/admin/profiles`. Recoverable right
> up until an expert answers, and not one minute after.

**Then the courses**, in two ways, because the two formats are not reachable the same way:

```bash
CONFIRM=<host> task instance:courses:v1    # a spreadsheet of URLs
CONFIRM=<host> task instance:courses:v2    # a tree on this machine
CONFIRM=<host> task instance:deployments   # where each one is deployed
```

- **`LearnpackV1`, from URLs.** Locators stay public, so this store can read those packages
  again by itself later.
- **`LearnpackV2`, from a local tree.** The generator's run output is served nowhere, so it is
  read off disk — which takes **two processes**: `task backend` serving the tree in local mode,
  and the task above writing to the deployed store. Its locators end up pointing at
  `localhost`, which costs a campaign nothing (the evaluator's screen reads the stored profile
  and fetches nothing) and means only that the deployed API can never re-read those packages.
- **Deployments last**, because a course is usually deployed after it is registered. Its
  `external_id` is declared by the package and printed by the registration, so the CSV —
  `external_id,url` — is written *after* the two steps above, not before.

[Registering courses](README.md#registering-courses) and
[Declaring the deployment](README.md#declaring-the-deployment-of-a-registered-course-declare-deployment)
describe the commands underneath and what the files look like.

> ⚠️ **Before opening the campaign, read `/admin/profiles`** and confirm no course was left
> unread. A package that failed to be read says so only there and in the summary line the
> command printed at the time.

## 8. The campaign

From the console, both of them:

- **Invite the evaluators** from `/admin/assessors` — see
  [Inviting evaluators](#inviting-evaluators-adr-0049).
- **Open the campaign** and assign.

Before inviting anyone real, run one course through end to end yourself: it is the only way to
see that the course loads inside the frame from this origin, and that the right items are
withheld from it.

---

## After it is running

### Releasing

**Pushing releases nothing.** Neither host watches this repository, and an image-backed service
does not redeploy when a new image appears under its tag — so a release is an act somebody
performs:

```bash
task deploy:api        # builds, publishes the image, triggers the release
task deploy:console    # builds and publishes the site
```

Without a `RENDER_DEPLOY_HOOK` declared, `deploy:api` publishes and then says so — the release
is *Manual Deploy* in the dashboard.

A release **never touches the store**: Neon is its own service and nothing in a deploy writes
data. What moves with the code is the schema, and the pre-deploy command is what moves it:
`alembic upgrade head`, once, before traffic switches. If it fails Render halts the release and
the previous version keeps serving — which is why it is not in the start command, where a
half-migrated schema would meet live traffic.

The seeders are not in that path and must not be: `seed` is idempotent, but a step that reruns
on every release is a step nobody reads the output of.

### Backing up

**Before every release while a campaign is open:**

```bash
CONFIRM=<the neon host> task instance:dump
```

The migrations here do not destroy data, but that is a convention rather than a guarantee, and
this is thirty seconds against the only copy of what the panel answered. It writes outside the
repository, to `DUMP_DIR`, deliberately: the dump is the **identified** record — it carries
every expert's address — and it is what the campaign's results are read from once this instance
is gone.

### When somebody leaves (ADR-0051)

Deactivate them from `/admin/assessors`. Nothing is deleted — their evaluations and the reports
naming them are what happened, and an `Assessor` is the key of provenance — but they are
offered no new work and every request they make answers 403. Reversible from the same row.

It does **not** cancel their open assignments; that lives in campaigns and stays a manual step.

---

## Reference

### Roles and the first admin (ADR-0007)

`assessors.role` is the source of truth for authorization, and **login never changes anyone's
role** — authenticating cannot escalate privileges.

`ADMIN_EMAILS` is a **provisioning** allowlist, not an authorization one. It only decides the
role a **new** assessor is created with:

- On the list, never signed in → created as `admin`.
- On the list but already exists as `evaluator` → **stays** `evaluator`.
- An existing `admin` removed from the list → **stays** `admin`.
- No `email` claim (missing JWT template) → `evaluator`.

This is safe **because access is invite-only**: nobody can register with an admin's email
without the invitation. If you ever disable invite-only, revisit ADR-0007.

Changing an existing assessor's role is done from `/admin/assessors` (ADR-0050), with two
refusals that are enforced because neither is recoverable from inside the product: nobody
changes their own role, and the last admin cannot be demoted. Every grant records its author.
`set-role` is the break-glass version and enforces neither — which is the point of a
break-glass tool, and the reason not to reach for it when a screen would do.

### Inviting evaluators (ADR-0049)

Inviting somebody creates **no account**: it records the address, the role and the expertise
profile, and the `assessors` row appears at that address's first login already carrying them.
From `/admin/assessors`, or here:

```bash
uv run python -m app.cli invite-assessor --email ada@yourcompany.com \
    --role evaluator --name "Ada Lovelace" --expertise "Instructional design"
uv run python -m app.cli list-invitations
```

Redeemable for seven days, at most one pending per address; re-sending reopens a window that
closed, revoking frees the address. With `CLERK_SECRET_KEY` set this **also creates the Clerk
invitation**, so it is one act — do not also invite them in Clerk by hand.

The link lands on **`/accept-invitation`**, which renders a sign-up. That is not a detail:
somebody accepting an invitation has no account yet, so Clerk hands the ticket over as
`__clerk_status=sign_up` and a page rendering the sign-in form renders and spins for ever.
Point Clerk's `NEXT_PUBLIC_CLERK_SIGN_UP_URL` at the same route.

> ⚠️ **Delivery can fail without the invitation failing.** Clerk refuses an address that is
> already a Clerk user, and that rule cannot be bypassed. The invitation is created here either
> way and the answer says `delivered: false` with Clerk's own sentence; the remedies are
> **Re-send**, or inviting that person in Clerk by hand.

**The invitation is where the panel is told what happens to what they write**, because it is
the last moment before they can start. Clerk's email is the one they receive, so the notice goes
in that template, in the Clerk dashboard — nothing here composes it. One sentence is enough:

> Your answers and comments are read by our team alongside the other reviewers', under an
> identifier rather than your name.

The evaluator's screen carries the short half of it (`Your answers are recorded under an
identifier, not your name`). Keep the two saying the same thing: if what is shared ever widens,
this sentence changes first, and it can only change for people invited after it.

### The JWT template, in detail

Clerk's default session token **carries neither email nor name**. The template adds them:

```json
{
  "email": "{{user.primary_email_address}}",
  "name": "{{user.full_name}}",
  "email_verified": "{{user.email_verified}}"
}
```

`setup-clerk-jwt-template` needs `CLERK_SECRET_KEY` and nothing else — not `AUTH_MODE`, because
the act belongs to the instance that key names and not to the process running it. `--name` is
for a template called something other than `learnpack-evals`; it has to match the frontend's
`NEXT_PUBLIC_CLERK_JWT_TEMPLATE`, because `getToken({ template })` against a name Clerk does not
have returns nothing at all and the request then arrives unauthenticated rather than wrong.

`email` decides the first admin's initial role. `email_verified` gates one thing: **redeeming an
invitation** — matching an invitation on an address the provider never vouched for is a known
account-takeover shape, which is why the claim is required rather than assumed. Quoted or
unquoted both work; the backend reads a real boolean and the string `"true"` alike and,
deliberately, reads `"false"` as false.

**Getting it wrong is quiet**: the person signs in and appears in the roster with the *default*
role while their invitation still says `pending`, because an invitation is consumed only while
the assessor is being created. The backend logs a warning naming this template every time it
declines to redeem, and the console marks such an invitation.

### Rehearsing Clerk against your own machine

Clerk's **development** instance is built for `localhost`, so the sign-in and invitation flows
can be exercised without deploying anything. The only guard is the reverse one: `AUTH_MODE=local`
refuses a remote database and `ENVIRONMENT=production`.

`backend/.env`:

```text
AUTH_MODE=clerk
CLERK_ISSUER=https://<your-app>.clerk.accounts.dev
CLERK_SECRET_KEY=sk_test_...
# DATABASE_URL stays the local container; ALLOWED_ORIGINS already covers localhost:3000
```

`frontend/.env.local`:

```text
NEXT_PUBLIC_AUTH_MODE=clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
```

Then write the template — `uv run python -m app.cli setup-clerk-jwt-template` — before signing
in for the first time. It works from here because a development instance is a real instance.

What changes: the user picker is gone and you sign in as a real person; `GET /dev/identities`
and the rest of the dev-only surface answer 404; `seed-demo` refuses to run; and inviting from
the console really sends an email.

The two modes share one database and cannot collide — a local assessor is stored as
`('local', <email>)` and a Clerk one as `('clerk', <sub>)`, so the same person signing in both
ways is two assessors, which is what you want on a dev box.
