# Deploying an instance

A human evaluation campaign: subject-matter experts open a course in a browser and score it.

Two things get deployed. **The API**, on Render with its database on Neon, and **the console**
— the web application people open: the admin screens and the evaluators' own — on Netlify,
with Clerk for identity. That is what "console" means throughout.

**Follow this top to bottom, once per instance.** Three of the steps degrade *silently* if they
run late; one of them stops being repairable the moment an expert answers.

Measuring a generator's output needs none of it — that runs on your machine in local mode.

## Before you start

Have these ready. Everything else — the Neon project, the Render service, the Netlify site,
Clerk's production instance — is created at its step.

| | |
|---|---|
| **Accounts** | **Neon**, **Render** (with billing set up: step 4 needs a **paid** instance type), **Netlify**, and **Clerk** with an application created in it — step 3 adds that application's production instance |
| **Netlify's CLI** | `npm i -g netlify-cli`, then `netlify login` |
| **Docker**, running | it builds the API image (step 1) and runs the backup (`instance:dump`) |
| **A domain you control at its registrar** | Clerk's production instance requires one, and step 3 points its nameservers at Netlify. **Its DNS can take up to 48 hours to propagate** |
| **Two GitHub tokens** | **Classic** personal access tokens, from any account: one scoped `write:packages` (step 1), one scoped `read:packages` (step 4) |
| **The first admin's email address** | used at steps 3 and 4 |
| **The courses** | by step 7: the V1 courses as public URLs, the V2 courses as the generator's output on this machine, and for each V2 course the URL it is deployed at — an expert opens every course in a browser |

Everything below runs **on your own machine**, never from a shell on the server. A `task …`
works from anywhere in the repository; where a bare command has to run somewhere in
particular, the step says where.

> To rehearse identity first — JWT template, first admin, an invitation redeemed — do
> [Clerk against your own machine](README.md#clerk-against-your-own-machine) **before step 1**.
> Nothing done there reaches the instance built here.

---

## 1. Publish the API image

From `backend/`, create the instance file and fill in `IMAGE_REPO` — `.env.instance.example`
says what it has to satisfy:

```bash
cp .env.instance.example .env.instance
```

**`backend/.env.instance` is filled in as you go**: every step below that hands you a value
says to write it there.

Log in to the registry, giving the `write:packages` token as the password, and publish:

```bash
docker login ghcr.io -u <your github user>
task deploy:api
```

`deploy:api` refuses while anything tracked is uncommitted: it tags the image with the commit.
The first push creates the package; afterwards, **check in GitHub that it is private**.

## 2. The database (Neon)

Create the project:

| | |
|---|---|
| **Postgres version** | **17** |
| **Region** | Choose it here; Render's service goes in the same one at step 4. Neon names regions after AWS, Render after cities: Virginia is `us-east-1`, Ohio `us-east-2`, Oregon `us-west-2`, Frankfurt `eu-central-1`, Singapore `ap-southeast-1` |
| **Enable Neon Auth** | **Leave it off** |

Copy the connection string from the project's **Connect** panel. It goes in two places:
`DATABASE_URL` in `backend/.env.instance` **now**, and Render's environment at step 4.

Neon hands you a `postgresql://…` string. Change the driver prefix to `postgresql+psycopg://`;
keep `?sslmode=require`:

```text
DATABASE_URL=postgresql+psycopg://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Do not create tables. The API's first release runs the migrations (step 4).

## 3. Clerk and the domain — all of it before anybody signs in

Do this **before everything that follows**. Two waits start here and each can take up to 48
hours: the nameservers, and the records Clerk verifies.

The domain is the console's. The API stays on `onrender.com`.

1. **In the Netlify dashboard**, go to **DNS → Use Netlify DNS**, enter the domain name and
   click **Verify**.
2. **Point the registrar at it.** Netlify answers with four nameservers; set those where the
   domain was bought, replacing what is there — registrars usually call it *custom DNS*.
3. **In Clerk, create the production instance** for your application, giving it the domain
   from (1). Then go to **Developers → Domains → Configure**: Clerk lists five CNAME records.
   Add each one to the Netlify DNS from (1), exactly as shown — a single character out and
   the record stays unverified; Clerk's **AI prompt** button copies them out as text. Then
   press **Verify** in Clerk.
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

   Re-runnable. What it writes is [in the reference](#the-jwt-template-in-detail).
6. **In Clerk**, under **User & Authentication → Access Mode**, set it to **Invite-only**.
7. **Invite the admin**, from Clerk's **Invitations** page, at the address you chose for the
   first admin. This is Clerk's invitation only: the `assessors` row appears when they sign
   in, at step 6.

> ⚠️ **The JWT template (5) must exist before the admin's first login.** Without it the admin
> is created as an `evaluator`, and writing the template afterwards does not change that
> (step 6 has the repair).

**Nobody signs in yet.**

## 4. The API (Render)

In the Render dashboard, **New → Web Services**. On the form, under **Source Code**, click
**Existing Image**, give it your `IMAGE_REPO:latest` and the `read:packages` token, and press
**Connect**.

The rest of the form:

| Field | Value |
|---|---|
| Region | the one Neon is in (step 2) |
| Instance type | any **paid** one — the pre-deploy command does not exist on free |
| Health check path | `/livez` — **not** `/health`: Render probes it every few seconds, and `/health` queries the database, so Neon's compute would never suspend and would bill the whole month |
| Pre-deploy command | `alembic upgrade head` |

And its environment:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `AUTH_MODE` | `clerk` |
| `DATABASE_URL` | from step 2 |
| `CLERK_ISSUER` | `https://clerk.<your domain>`, from step 3 |
| `CLERK_SECRET_KEY` | the `sk_live_…` key from step 3. Without it invitations are never created in Clerk |
| `ADMIN_EMAILS` | the first admin's address. It decides the role a **new** assessor is created with, and never changes an existing one |
| `ALLOWED_ORIGINS` | `https://<your domain>`. If you add more, this one stays **first**: the first entry is also where Clerk's invitation link lands |

**Leave unset:** `CLERK_JWKS_URL`, `LLM_API_KEY` and `LOCAL_SOURCE_ROOTS`.

**Optional: the AI inside the course.** Left unset, the evaluator's course loads without its AI
and the screen says why. To turn it on, set the four variables described in `.env.example` —
an academy, a **non-SaaS** cohort, a service account and its role, created by hand:

```text
BREATHECODE_SERVICE_TOKEN=
BREATHECODE_ACADEMY_ID=
BREATHECODE_COHORT_ID=
SEAT_EMAIL_TEMPLATE=you+sme-{slug}@yourdomain.com
```

> ⚠️ **All four, or none.** With the three `BREATHECODE_*` set and `SEAT_EMAIL_TEMPLATE` empty,
> the feature switches on and fails one evaluator at a time, on their screen. The template
> must contain `{slug}`.

`BREATHECODE_API_URL`, `RIGOBOT_API_URL` and `RIGOBOT_ORGANIZATION` have working defaults;
declare them only if yours differ.

Once the first release is live, open `https://<the service>.onrender.com/health` in a
browser. `{"status": "ok", "environment": "production"}` means the API reaches the database
and the schema is in. That URL is the API's address, which step 5 needs.

Two values for `backend/.env.instance` come out of this step: **`ADMIN_EMAIL`**, the same
address as `ADMIN_EMAILS` here, and **`RENDER_DEPLOY_HOOK`** from the service's *Settings →
Deploy Hook*.

## 5. The console (Netlify)

From **`frontend/`**, where `netlify.toml` is — every `netlify` command in this step runs there:

```bash
netlify sites:create --name <the site>
netlify link
```

**Attach the domain** from step 3 to this site: in the Netlify dashboard, the site's **Domain
management → Add a domain**.

**Set the environment** under the site's **Site configuration → Environment variables** —
the Clerk keys come from step 3, the API's URL from step 4:

```text
NEXT_PUBLIC_AUTH_MODE=clerk
NEXT_PUBLIC_API_URL=https://<the render service>.onrender.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/accept-invitation
```

**All of it is read at build time**: changing any of it needs a new release. A site published
before they exist points at `localhost` with no Clerk key, and says nothing about it.

`NEXT_PUBLIC_AUTH_MODE` is declared even though anything other than `local` means Clerk
anyway, because a variable the site leaves undeclared is not therefore absent from the build:
the build runs on a developer's machine, and an env file there fills whatever the process does
not already carry. Declaring it is what makes the site, and not that machine, the one that
answers the question.

> ⚠️ **Do not tick "Contains secret values" on any of them.** A build on this machine receives
> the masked string (`****************abcd`) instead of the value, and bakes that in. A
> variable already marked secret cannot be unmarked — delete it and create it again.

Check the wiring before publishing — `netlify build --dry` from `frontend/` builds nothing and
prints what a real build would do:

- **Config file** is `frontend/netlify.toml`, and **Current directory** is `frontend`.
- **Next.js Runtime** appears among the plugins. Without it the site publishes and its
  server-rendered routes do not work.

Then publish with `task deploy:console`, or `task deploy:console:preview` for a draft URL that
leaves the live site alone. **A draft cannot sign anybody in**: Clerk's production instance
answers only its own domain, and the page spins at *Signing you in…*. A draft proves that the
build runs and the server function answers; sign-in is checked at step 6.

## 6. The first admin signs in

Now, and not before. The admin opens the invitation email from step 3, creates their account,
and signs in at `https://<your domain>`. **The console lands an admin on `/admin`** and an
evaluator on `/evaluations`, so the landing page is the check.

The tasks from here on act as `ADMIN_EMAIL` (`backend/.env.instance`), so this row has to
exist first.

**If they landed as an `evaluator`**, with `DATABASE_URL` and `ADMIN_EMAIL` in
`backend/.env.instance`:

```bash
CONFIRM=<the neon host> task instance:promote-admin
```

**`<the neon host>` is the host part of `DATABASE_URL`** — what sits between the `@` and the
next `/`, `ep-xxx.region.aws.neon.tech` in the shape step 2 showed. Every task that writes to
the deployed database prints that host and stops if `CONFIRM` does not name it. Run it once
bare and it tells you what to type:

```text
$ task instance:promote-admin
This writes to ep-xxx.region.aws.neon.tech, as ada@yourcompany.com (AUTH_MODE=clerk).
Re-run with CONFIRM=ep-xxx.region.aws.neon.tech to say that is the store you meant.

$ CONFIRM=ep-xxx.region.aws.neon.tech task instance:promote-admin
```

The same `CONFIRM=<the neon host>` precedes every `instance:*` task from here on.

## 7. Seed the database and register the courses

Five tasks, in this order, all from anywhere in the repository. Every one prints the host it is
about to write to and refuses until `CONFIRM` names it, as step 6 showed.

### 7.1 Complete `backend/.env.instance`

This step reads the last block of the file:

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

> ⚠️ **`instance:seed` goes before any course is registered.**

### 7.3 The V1 courses, from a list of URLs

Write `backend/courses-v1.csv`: **one course URL per row, in the first column**. A header
row, blank lines, other columns and rows starting with `#` are ignored. Then:

```bash
CONFIRM=<the neon host> task instance:courses:v1
```

Every course is attributed to `GENERATOR_NAME` `GENERATOR_VERSION_V1`. The URL a V1 course is
registered from is recorded as its deployment too: these courses need nothing at 7.5.

### 7.4 The V2 courses, from the generator's tree

The tree is the folder `LOCAL_SOURCE_ROOTS` points at, laid out the way the generator writes
it: one folder per run named `<GENERATOR_NAME>-<version>` (`learnpack-generator-04a7dd5`, for
example), and one course folder inside each. The version is read off the run folder's name.

**Everything in the tree is registered, and there is no picking.** Every top-level folder
has to be a run folder named that way — one that is not aborts the whole run — and every
folder inside a run is registered as a course. Point `LOCAL_SOURCE_ROOTS` at a folder that
holds only the runs and courses this campaign wants. Re-running is safe: an unchanged course
is a reported no-op.

1. In a second terminal, start the local API and leave it running: `task backend`.
2. Then:

   ```bash
   CONFIRM=<the neon host> task instance:courses:v2
   ```

**Keep the output**: it prints each course's `external_id`, which 7.5 needs.

### 7.5 Where each V2 course is deployed

Write `backend/deployments.csv`, **two columns, `external_id,url`**: the id printed at 7.4, and
the URL the course is deployed at. A header row is allowed. Then:

```bash
CONFIRM=<the neon host> task instance:deployments
```

Until a course has a deployment it cannot be assigned to anyone.

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

Before inviting anyone real, run one course through end to end yourself: that the course loads
inside the frame from this origin, and that the right items are withheld from it.

---

## After it is running

### Releasing

**Pushing releases nothing.** A release is an act somebody performs:

```bash
task deploy:api        # builds, publishes the image, triggers the release
task deploy:console    # builds and publishes the site
```

Without a `RENDER_DEPLOY_HOOK` declared, `deploy:api` publishes and then says so — the release
is *Manual Deploy* in the dashboard.

A release **never touches the database**. The pre-deploy command runs the migrations before
traffic switches; if it fails, Render halts the release and the previous version keeps serving.

Re-run `CONFIRM=<the neon host> task instance:seed` (7.2) when the repo changes any of:
the questions an expert is asked, the pedagogical reference those questions rest on, or
what the instance needs in order to read a course (new data a format extracts, or a newly
accepted reader). A code-only release does not.

### Backing up

**Before every release while a campaign is open:**

```bash
CONFIRM=<the neon host> task instance:dump
```

It writes to `DUMP_DIR`, outside the repository: the dump carries every expert's address.
`pg_dump` runs from the `postgres:17-alpine` image; nothing has to be installed.

### When somebody leaves (ADR-0051)

Deactivate them from `/admin/assessors`. Nothing is deleted. Reversible from the same row.

It does **not** cancel their open assignments; that lives in campaigns and stays a manual step.

---

## Reference

### Roles and the first admin (ADR-0007)

`assessors.role` is the source of truth. **Login never changes anyone's role.**

`ADMIN_EMAILS` only decides the role a **new** assessor is created with:

- On the list, never signed in → created as `admin`.
- On the list but already exists as `evaluator` → **stays** `evaluator`.
- An existing `admin` removed from the list → **stays** `admin`.
- No `email` claim (missing JWT template) → `evaluator`.

Changing an existing assessor's role is done from `/admin/assessors` (ADR-0050): nobody
changes their own role, and the last admin cannot be demoted. `set-role` is the break-glass
version and enforces neither.

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
invitation** — do not also invite them in Clerk by hand.

The link lands on **`/accept-invitation`**. The console's `NEXT_PUBLIC_CLERK_SIGN_UP_URL`
points at the same route.

> ⚠️ **Delivery can fail without the invitation failing.** Clerk refuses an address that is
> already a Clerk user. The invitation is created here either way and the answer says
> `delivered: false` with Clerk's own sentence; the remedies are **Re-send**, or inviting that
> person in Clerk by hand.

### The JWT template, in detail

```json
{
  "email": "{{user.primary_email_address}}",
  "name": "{{user.full_name}}",
  "email_verified": "{{user.email_verified}}"
}
```

`setup-clerk-jwt-template` needs `CLERK_SECRET_KEY` and nothing else. `--name` is for a
template called something other than `learnpack-evals`; it has to match
`NEXT_PUBLIC_CLERK_JWT_TEMPLATE`.

`email` decides the first admin's initial role. `email_verified` gates **redeeming an
invitation**. Quoted or unquoted both work.

**Getting it wrong is quiet**: the person signs in and appears in the roster with the *default*
role while their invitation still says `pending`. The backend logs a warning naming this
template every time it declines to redeem, and the console marks such an invitation.

---

## When something does not work

Everything here fails **quietly**: a screen that looks fine, or a check that never passes, and
no reason.

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
| The console shows *missing bearer token* on `/`, and an anonymous visitor gets `200` instead of a redirect to `/sign-in` | The deploy carries no edge functions: the CLI reads them from `.netlify/` under the directory it was run from, and the build wrote them somewhere else | Run the deploy from `frontend/`, where `netlify.toml` is — `task deploy:console` does. `netlify api getDeploy` on the deploy shows `edge_functions_present: true` when it worked |
| The console spins at *Signing you in…* and Clerk answers `400 origin_invalid` | The page is open on an origin that is not the domain — a `netlify.app` draft or the site's default address | Open it at `https://<your domain>`; a draft URL can never sign in |
| Every expert is asked all twelve items | The extraction was accepted **after** the courses were registered, so they were never profiled | Read them from `/admin/profiles` — and only answers given before that are affected, which cannot be undone |
