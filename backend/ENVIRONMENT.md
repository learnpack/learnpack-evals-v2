# Deploying an instance

One errand: **a human evaluation campaign**, where subject-matter experts who do not have this
repository open a course in a browser and score it. That needs real accounts and somewhere to
keep what they answer — so it needs Clerk, a store and two hosts.

Two things get deployed. **The API**, which holds everything, and **the console** — the web
application people open: the admin screens and the evaluators' own. That is what "console"
means throughout.

**Follow this top to bottom, once per instance.** The order is not a preference: three of the
steps degrade *silently* if they run late, and one of them stops being repairable the moment an
expert answers.

Measuring a generator's output needs none of it — that runs on your machine in local mode.

## Before you start

All of this lives outside the repository:

| | |
|---|---|
| **Neon** | a project, in the region the API will run in |
| **Render** | an account on a **paid** instance type: the pre-deploy command that runs the migrations does not exist on free |
| **Netlify** | an account, and its CLI (`npm i -g netlify-cli`, then `netlify login`) |
| **A domain you can add DNS records to** | Clerk's production instance requires one, and **its DNS can take up to 48 hours to propagate** — which is why step 3 comes first. Without a domain you are on a development instance: 100 users, emails prefixed `development`, and the session carried in the querystring instead of a cookie |
| **A GitHub account to publish the image from** | Any account; it needs no relation to this repository. Two **classic** tokens — `write:packages` for you (step 1), `read:packages` for Render (step 4) |
| **The courses, deployed** | An expert opens them in a browser, so each one needs a URL (ADR-0028) |
| **The first admin's email address** | |

Everything below runs **on your own machine**, never from a shell on the server: the image is
built from `backend/` alone, so the seeder's own files are not inside it. A `task …` works from
anywhere in the repository; where a bare command has to run somewhere in particular, the step
says where.

> **Rehearse first if you can.** The identity half — the JWT template, the first admin, an
> invitation redeemed — is the part whose order cannot be repeated, and all of it can be
> exercised against `localhost` before any of this exists. See
> [Rehearsing Clerk against your own machine](#rehearsing-clerk-against-your-own-machine).

---

## 1. Publish the API image

Render does not build this repository; it runs a **prebuilt image**, and one has to exist before
a service can point at it.

**Nothing is created by hand**: the first push creates the package. From `backend/`, create
the instance file and fill in `IMAGE_REPO` — the name the image is published under, and
`.env.instance.example` says what it has to satisfy:

```bash
cp .env.instance.example .env.instance
```

**`backend/.env.instance` is filled in as you go**, not at the end: every step below that hands
you a value says to write it there, and by step 7 the file is complete.

Then log in to the registry, giving the **classic** token scoped `write:packages` as the
password — GHCR refuses fine-grained ones — and publish:

```bash
docker login ghcr.io -u <your github user>
task deploy:api
```

`deploy:api` refuses while anything tracked is uncommitted — it tags the image with the commit,
and a tag that misdescribes its contents outlives the chance to notice.

Afterwards, **check in GitHub that the package is private**. Storage and bandwidth for the
container registry are free today, so the image's size does not matter.

## 2. The store (Neon)

Create the project. Three of its options matter:

| | |
|---|---|
| **Postgres version** | **17** — what the test suite and the local container run, so it is the version everything here is tested against |
| **Region** | **You choose it here**, and Render's service goes in the same one at step 4. Neon names regions after AWS and Render after cities: Virginia is `us-east-1`, Ohio `us-east-2`, Oregon `us-west-2`, Frankfurt `eu-central-1`, Singapore `ap-southeast-1` |
| **Enable Neon Auth** | **Leave it off.** Identity here is Clerk's job, and this would add tables of its own to the database for nothing |

One region for both because **the API queries the database many times per request**, so that
distance is paid over and over. The distance to whoever is browsing is paid once, and barely
shows.

Then copy the connection string from the project's **Connect** panel. It goes in two places:
`DATABASE_URL` in `backend/.env.instance` **now**, and Render's environment at step 4. **Neon
hands you a `postgresql://…` string, and it needs one edit** — the driver prefix becomes
`postgresql+psycopg://`, keeping the `?sslmode=require` that is already there:

```text
DATABASE_URL=postgresql+psycopg://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Nothing migrates it by hand. The API's pre-deploy command is `alembic upgrade head`, so the
first release is also the first migration.

## 3. Clerk and the domain — all of it before anybody signs in

**First of everything that follows.** Two waits start here and each can take up to 48 hours:
the nameservers, and the records Clerk verifies. Left for later they land on the day you meant
to open the campaign.

**One domain, and it is the console's.** Clerk serves its Frontend API from `clerk.<your
domain>` because if the two were not same-site the session cookie would need `SameSite=None`,
which Safari does not accept. The **API stays on `onrender.com`** — its token travels in the
`Authorization` header, so it is cross-origin by design and needs no domain.

1. **In the Netlify dashboard**, go to **DNS → Use Netlify DNS**, enter the domain name and
   click **Verify**.
2. **Point the registrar at it.** Netlify answers with four nameservers; set those where the
   domain was bought, replacing what is there — registrars usually call it *custom DNS*.
3. **In Clerk, create the production instance** for your application, giving it the domain
   from (1). Then go to **Developers → Domains → Configure**: Clerk lists five CNAME records.
   Add each one to the Netlify DNS from (1), exactly as shown — a single character out and
   the record stays unverified; Clerk's **AI prompt** button copies them out as text, which
   beats transcribing. Then press **Verify** in Clerk.
4. **Collect the production keys.** Under **Developers → API Keys**, the production instance
   has a publishable key (`pk_live_…`) and a secret key (`sk_live_…`). Three values leave this
   step, and later steps ask for them by name:

   | Value | Where it goes |
   |---|---|
   | `CLERK_SECRET_KEY` (`sk_live_…`) | `backend/.env.instance` **now**; Render at step 4; Netlify at step 5 |
   | `CLERK_ISSUER`, which is `https://clerk.<your domain>` | Render at step 4 |
   | The publishable key (`pk_live_…`) | Netlify at step 5 |

5. **Write the JWT template.** With `CLERK_SECRET_KEY` in `backend/.env.instance`:

   ```bash
   task instance:clerk-template
   ```

   It creates the template, updates it, or reports it unchanged, and can be run again at any
   time. What it writes and why is [in the reference](#the-jwt-template-in-detail).
6. **In Clerk**, under **User & Authentication → Access Mode**, set it to **Invite-only**.
7. **Invite the admin**, from Clerk's **Invitations** page, at the address you chose for the
   first admin. Invite-only means nobody can sign themselves up, so the first account has to
   arrive this way. This invitation only gets them through Clerk's door: the `assessors` row
   appears when they sign in, at step 6, and there is no backend yet to run `invite-assessor`
   against.

> ⚠️ **The JWT template (5) must exist before the admin's first login.** Without the `email`
> claim the assessor is created as an `evaluator` — a safe degrade — and `ADMIN_EMAILS` applies
> once, at row creation, so writing the template afterwards rescues nobody.

**Nobody signs in yet.**

## 4. The API (Render)

In the Render dashboard, **New → Web Services**. On the form, under **Source Code**, click
**Existing Image**, give it your `IMAGE_REPO:latest` and the `read:packages` token, and press
**Connect**.

The rest of the form:

| Field | Value |
|---|---|
| Region | the one Neon is in (step 2) |
| Instance type | any **paid** one |
| Health check path | `/health` |
| Pre-deploy command | `alembic upgrade head` |

And its environment:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `AUTH_MODE` | `clerk`. Declared rather than left to the default, so a refusal is never what discovers it: `local` here does not boot at all (ADR-0008) |
| `DATABASE_URL` | Neon, from step 2 |
| `CLERK_ISSUER` | `https://clerk.<your domain>`, from step 3 |
| `CLERK_SECRET_KEY` | the `sk_live_…` key from step 3. Without it an invitation is recorded here and never created in Clerk, so the person invited cannot sign in at all (ADR-0049) |
| `ADMIN_EMAILS` | the first admin's address. Provisioning, not authorization: it decides the role a **new** assessor is created with and never changes an existing one (ADR-0007) |
| `ALLOWED_ORIGINS` | `https://<your domain>`, the console's origin from step 3. If you add more, this one stays **first**: the first entry is both what CORS allows and where Clerk's invitation link lands, and an invitation that lands on the wrong origin is found by the one person who cannot accept it |

**What is deliberately absent:** `CLERK_JWKS_URL` (empty, it is derived from the issuer; a
value copied from a local `.env` silently wins and points this instance at a development one) ·
`LLM_API_KEY` (no assessor judges from here) · `LOCAL_SOURCE_ROOTS` (local trees are served
only under `AUTH_MODE=local`).

**The AI inside the course is optional, and takes four variables.** Left unset, the
evaluator's course loads without its AI and the screen says why. Set them if the seats exist —
an academy, a **non-SaaS** cohort, a service account and its role, created by hand and
described in `.env.example`:

```text
BREATHECODE_SERVICE_TOKEN=
BREATHECODE_ACADEMY_ID=
BREATHECODE_COHORT_ID=
SEAT_EMAIL_TEMPLATE=you+sme-{slug}@yourdomain.com
```

> ⚠️ **Only the first three decide whether course sessions are on.** Set those and leave
> `SEAT_EMAIL_TEMPLATE` empty and the feature switches on anyway — then fails one evaluator at
> a time, on their screen, when the seat cannot be given an address. It must contain `{slug}`,
> which is what makes each seat's address its own.

`BREATHECODE_API_URL`, `RIGOBOT_API_URL` and `RIGOBOT_ORGANIZATION` have working defaults;
declare them only if yours differ.

Once the first release is live, open `https://<the service>.onrender.com/health` in a
browser. `{"status": "ok", "environment": "production"}` says the schema and the store are
both there — it runs a real query, so it cannot answer `ok` over a database it cannot reach.
That URL is the API's address, which the console needs at step 5.

Two values for `backend/.env.instance` come out of this step: **`ADMIN_EMAIL`**, the same
address as `ADMIN_EMAILS` here, and **`RENDER_DEPLOY_HOOK`** from the service's *Settings →
Deploy Hook*, which is what lets `task deploy:api` release without the dashboard.

## 5. The console (Netlify)

Netlify does not build this repository either, so the site is created and published from here.
`frontend/netlify.toml` declares the build and the Node version, and the CLI reads it exactly
as a hosted build would.

**From `frontend/`**, and every `netlify` command in this step runs there: the CLI looks for
`netlify.toml` in the directory it is run from, `netlify link` records the site there, and the
deploy picks up the edge functions only when that directory is also the one the build ran in:

```bash
netlify sites:create --name <the site>
netlify link
```

**Attach the domain** from step 3 to this site: in the Netlify dashboard, the site's **Domain
management → Add a domain**. Its DNS is already at Netlify, so this is the record that points
the domain at what you are about to publish.

**Set the environment** under the site's **Site configuration → Environment variables** —
the Clerk keys come from step 3, the API's URL from step 4. **All of it is read at build
time**, so changing any of it needs a new release rather than a restart:

```text
NEXT_PUBLIC_API_URL=https://<the render service>.onrender.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/accept-invitation
```

`NEXT_PUBLIC_AUTH_MODE` is left unset on purpose: anything that is not `local` is `clerk`, so a
missing or misspelled value fails safe.

> ⚠️ **Do not tick "Contains secret values" on any of them.** A secret value never leaves
> Netlify's own builders: what the CLI hands a build on this machine is the masked string
> (`****************abcd`), and that is what would be baked into the bundle. The site is built
> here, so its variables have to be plain. A variable already marked secret cannot be unmarked
> — delete it and create it again.

Check the wiring before publishing anything — `netlify build --dry` from `frontend/` builds
nothing and prints what a real build would do:

- **Config file** is `frontend/netlify.toml`, and **Current directory** is `frontend`.
- **Next.js Runtime** appears among the plugins. Without it a Next site still publishes, and
  its server-rendered routes do not work.

Then publish with `task deploy:console`, or `task deploy:console:preview` for a draft URL that
leaves the live site alone. **A draft cannot sign anybody in**: its URL is on `netlify.app`,
and Clerk's production instance answers only its own domain — every call to
`clerk.<your domain>` comes back `400 origin_invalid` and the page spins at *Signing you in…*.
What a draft proves is that the build runs and the server function answers; sign-in is
checked on the live site, at `https://<your domain>`, at step 6.

> ⚠️ **The environment has to be set before the build, not after.** `NEXT_PUBLIC_*` values are
> baked into the bundle as it is built, so a site published before they exist points at
> `http://localhost:8000` — the client's fallback — with no Clerk key, and says nothing about
> it.

## 6. The first admin signs in

Now, and not before. The admin opens the invitation email from step 3, creates their account,
and signs in at `https://<your domain>`. **The console lands an admin on `/admin`** and an
evaluator on `/evaluations`, so the landing page is the check.

Everything below is attributed to somebody, so this row has to exist first: an act names its
author (ADR-0042), and `ADMIN_EMAIL` in `backend/.env.instance` is how the tasks find them.

**If the order went wrong** and they landed as an `evaluator`, there is nothing to delete and
no allowlist to touch. It needs `DATABASE_URL` and `ADMIN_EMAIL` in `backend/.env.instance`:

```bash
CONFIRM=<the neon host> task instance:promote-admin
```

**`<the neon host>` is the host part of `DATABASE_URL`** — what sits between the `@` and the
next `/`, `ep-xxx.region.aws.neon.tech` in the shape step 2 showed. You do not have to work
it out: every task that writes to the deployed store starts by printing that host and stops
if `CONFIRM` does not name it, so run it once bare and it tells you what to type:

```text
$ task instance:promote-admin
This writes to ep-xxx.region.aws.neon.tech, as ada@yourcompany.com (AUTH_MODE=clerk).
Re-run with CONFIRM=ep-xxx.region.aws.neon.tech to say that is the store you meant.

$ CONFIRM=ep-xxx.region.aws.neon.tech task instance:promote-admin
```

The same `CONFIRM=<the neon host>` precedes every `instance:*` task from here on, and it
always means this. These tasks live in the same file as `db:reset`, and typing the host is
what makes writing to the campaign's store instead of the local one a deliberate act.

That is the break-glass path — at this point there is no admin, so nobody could grant the role
from the console, and this command has none of the console's guardrails. Which is why it is
here and nowhere else.

## 7. Seed the store and register the courses

Five tasks, in this order, all from anywhere in the repository. Every one prints the host it is
about to write to and refuses until `CONFIRM` names it, as step 6 showed.

### 7.1 Complete `backend/.env.instance`

This step reads the last block of the file. What each variable needs:

| Variable | Default in `.env.instance.example` | What to do |
|---|---|---|
| `GENERATOR_NAME` | `learnpack-generator` | Keep it, unless the generator has another name |
| `GENERATOR_VERSION_V1` | `1.0.0` | **Set it** to the generator version the V1 courses were produced by |
| `COURSES_V1_CSV` | `./courses-v1.csv` | Keep it; the path is relative to `backend/`. The file is written at 7.3 |
| `V2_ROOT` | `generated` | Keep it. It is the name given to the tree in the next line |
| `LOCAL_SOURCE_ROOTS` | `generated=D:\generator\datasets\generated` | **Set the folder** to where the generator's output is on this machine, keeping the `generated=` prefix |
| `LOCAL_SOURCES_BASE_URL` | `http://localhost:8000/sources` | Keep it |
| `DEPLOYMENTS_CSV` | `./deployments.csv` | Keep it; relative to `backend/`. The file is written at 7.5 |
| `DUMP_DIR` | `../../learnpack-evals-dumps` | Keep it, or point it anywhere **outside** the repository. Used by [Backing up](#backing-up) |

Two more, because the V2 courses are read through the local API (7.4): in **`backend/.env`**,
the file `task backend` reads, set `AUTH_MODE=local` and add the **same** `LOCAL_SOURCE_ROOTS`
line.

### 7.2 Seed, and name the generator

```bash
CONFIRM=<the neon host> task instance:seed        # re-runnable
CONFIRM=<the neon host> task instance:generator   # once, ever
```

`instance:seed` installs the human reference instrument and the reference data, imports the
two instruments that declare the data a profile can name, and turns on automatic profiling
for both package formats. `instance:generator` registers the lineage `GENERATOR_NAME`, and
refuses to run twice.

> ⚠️ **`instance:seed` goes before any course is registered.**

### 7.3 The V1 courses, from a list of URLs

Write `backend/courses-v1.csv`: **one course URL per row, in the first column**. A header
row, blank lines, other columns and rows starting with `#` are ignored. Then:

```bash
CONFIRM=<the neon host> task instance:courses:v1
```

Every course is attributed to `GENERATOR_NAME` `GENERATOR_VERSION_V1`, and the version is
registered on the way if it does not exist yet. The URL a V1 course is registered from is the
running course, so it is recorded as its deployment too: these courses need nothing at 7.5.

### 7.4 The V2 courses, from the generator's tree

The tree is the folder `LOCAL_SOURCE_ROOTS` points at, laid out the way the generator writes
it: one folder per run named `<GENERATOR_NAME>-<version>` (`learnpack-generator-04a7dd5`, for
example), and one course folder inside each. The version is read off the run folder's name.

**Everything in the tree is registered, and there is no picking.** Every top-level folder
has to be a run folder named that way — one that is not aborts the whole run — and every
folder inside a run is registered as a course. So make the tree a folder of its own holding
only the runs and courses this campaign wants, copied from the generator's output, and point
`LOCAL_SOURCE_ROOTS` at it. Re-running is safe: an unchanged course is a reported no-op.

1. In a second terminal, start the local API and leave it running: `task backend`. It serves
   the tree; the task below reads through it and writes to the deployed store.
2. Then:

   ```bash
   CONFIRM=<the neon host> task instance:courses:v2
   ```

**Keep the output**: it prints each course's `external_id`, which 7.5 needs. The stored
locators point at `localhost`, which costs a campaign nothing: the evaluator's screen reads
the stored profile and fetches nothing.

### 7.5 Where each V2 course is deployed

A V2 course was read off disk, so nothing says where an evaluator opens it. Write
`backend/deployments.csv`, **two columns, `external_id,url`**: the id printed at 7.4, and the
URL the course is deployed at. A header row is allowed. Then:

```bash
CONFIRM=<the neon host> task instance:deployments
```

Until a course has a deployment it cannot be assigned to anyone. The task looks the ids up
among the V2 courses; for a V1 course deployed somewhere other than the URL it was registered
from, add `FORMAT=LearnpackV1`.

### 7.6 Check that every course was read

Open **`/admin/profiles`** in the console and confirm no course is marked unread. A package
that failed to be read says so only there and in the summary line the task printed. Unread
courses are profiled with `instance:reprofile` (7.2), or one at a time from that page.

[Registering courses](README.md#registering-courses) and
[Declaring the deployment](README.md#declaring-the-deployment-of-a-registered-course-declare-deployment)
describe the commands underneath.

## 8. The campaign

Both acts happen in the console:

- **Invite the evaluators** from `/admin/assessors` —
  [Inviting evaluators](#inviting-evaluators-adr-0049) says what can go wrong.
- **Open the campaign** from `/admin/campaigns` and assign courses to evaluators.

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
The console's `NEXT_PUBLIC_CLERK_SIGN_UP_URL` points at the same route.

> ⚠️ **Delivery can fail without the invitation failing.** Clerk refuses an address that is
> already a Clerk user, and that rule cannot be bypassed. The invitation is created here either
> way and the answer says `delivered: false` with Clerk's own sentence; the remedies are
> **Re-send**, or inviting that person in Clerk by hand.

**The evaluator's screen is where the panel is told what happens to what they write**: one
sentence under the rules they read before answering (`Your answers are recorded under an
identifier, not your name`), shown only once something is assigned to them. Clerk's invitation
email carries no notice, so its template needs no editing. If what is shared ever widens, that
sentence is the one to change.

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

The command rather than `task instance:clerk-template`, deliberately: the task reads the key
from `.env.instance`, which is the deployed instance's, and here the one you want is the
development key sitting in `backend/.env`.

What changes: the user picker is gone and you sign in as a real person; `GET /dev/identities`
and the rest of the dev-only surface answer 404; `seed-demo` refuses to run; and inviting from
the console really sends an email.

The two modes share one database and cannot collide — a local assessor is stored as
`('local', <email>)` and a Clerk one as `('clerk', <sub>)`, so the same person signing in both
ways is two assessors, which is what you want on a dev box.

---

## When something does not work

Everything here fails **quietly** — that is what earns it a place. A loud failure explains
itself; these hand you a screen that looks fine, or a check that never passes, and no reason.

| What you see | What it is | What to do |
|---|---|---|
| Clerk keeps saying `unverified` | The records are at a provider the domain does not point at, or they have not propagated | `nslookup -type=NS <your domain>` — `dns1.p0N.nsone.net` means Netlify. If that is right, `nslookup -type=CNAME clerk.<your domain>` and wait; propagation can take 48 hours |
| The admin signed in and is an `evaluator` | The JWT template was written after their first login, and `ADMIN_EMAILS` applies once, at row creation | `CONFIRM=<the neon host> task instance:promote-admin` |
| Somebody signs in with the default role while their invitation still says `pending` | The token carries no `email_verified` claim, so the invitation could not be redeemed | Fix the template (step 3.5) and re-send. The backend logs a warning naming it every time |
| An invitation answers `delivered: false` | That address is already a Clerk user, and Clerk refuses a second invitation for it | **Re-send**, or invite that person in Clerk by hand |
| The console loads, and every request to the API fails | Its origin is not in `ALLOWED_ORIGINS` | Add it on Render, **first** in the list |
| The console talks to `localhost` | It was published before its variables existed: `NEXT_PUBLIC_*` are baked in at build time | Set them in Netlify, then `task deploy:console` again |
| The build says the Clerk publishable key is invalid, and shows it as `****************abcd` | The variable is marked secret in Netlify, so the CLI handed the local build the mask instead of the value | Delete the variable and create it again without "Contains secret values" — the same for every other one marked secret |
| The course loads without its AI | One of the four seat variables is missing. If the three `BREATHECODE_*` are set and `SEAT_EMAIL_TEMPLATE` is not, it fails per evaluator instead of switching off | The evaluator's screen names the reason |
| The console shows *missing bearer token* on `/`, and an anonymous visitor gets `200` instead of a redirect to `/sign-in` | The deploy carries no edge functions, so the Clerk middleware never ran: the CLI reads them from `.netlify/` under the directory it was run from, and the build wrote them somewhere else | Run the deploy from `frontend/`, where `netlify.toml` is — `task deploy:console` does. `netlify api getDeploy` on the deploy shows `edge_functions_present: true` when it worked |
| The console spins at *Signing you in…* and Clerk answers `400 origin_invalid` | The page is open on an origin that is not the domain — a `netlify.app` draft or the site's default address — and the production instance refuses every other one | Open it at `https://<your domain>`; a draft URL can never sign in |
| Every expert is asked all twelve items | The extraction was accepted **after** the courses were registered, so they were never profiled | Read them from `/admin/profiles` — and only answers given before that are affected, which cannot be undone |

