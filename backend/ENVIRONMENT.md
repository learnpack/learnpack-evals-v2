# Deploying an instance

This is for one errand: **a human evaluation campaign**, where subject-matter experts who do
not have this repository open a course in a browser and score it. That needs real accounts and
somewhere to keep what they answer, so it needs Clerk, a store and two hosts — and everything
here is done **once per instance**: the hosts, the schema, the two things nothing in the app
can author, who is born an admin, how the evaluators are registered, and the order all of it
has to happen in.

Measuring a generator's output needs none of it. That runs on your machine in
[local mode](README.md#local-mode-and-clerk-mode-adr-0008), which replaces where identity comes
from and nothing else — so the campaign flow can be rehearsed locally first, and
[Running Clerk against your own machine](#running-clerk-against-your-own-machine) is how to
rehearse the sign-in and invitation halves too.

One Clerk instance is one instance.

**The commands here run from `backend/` on your own machine, pointed at the deployed store** —
`DATABASE_URL` at Neon and `AUTH_MODE=clerk` — not from a shell on the server. The image is
built from `backend/` alone, so `docs/seed/` is not in it and the seeder's own files are not
there to read.

## Clerk (ADR-0004)

Clerk's default session token **carries neither email nor name**. A **JWT template** adds them,
and writing it is a command rather than a form:

```bash
uv run python -m app.cli setup-clerk-jwt-template
```

It needs `CLERK_SECRET_KEY` and nothing else — not `AUTH_MODE`, because the act belongs to the
instance that key names and not to this process. It is idempotent, and says which of the three
things it did: created it, updated claims that had drifted, or left one that already said the
right thing. `--name` is there for a template called something other than `learnpack-evals`; it
has to match the frontend's `NEXT_PUBLIC_CLERK_JWT_TEMPLATE`, because `getToken({ template })`
against a name Clerk does not have returns nothing at all and the request then arrives
unauthenticated rather than wrong.

What it writes, and what the dashboard's own form would have to say:

```json
{
  "email": "{{user.primary_email_address}}",
  "name": "{{user.full_name}}",
  "email_verified": "{{user.email_verified}}"
}
```

The backend tolerates their absence (the profile stays `NULL`), but without them you cannot
identify the SMEs or use `set-role`.

`email_verified` gates one thing: **redeeming an invitation** (ADR-0049). Matching an
invitation on an address the provider never vouched for is a known account-takeover shape,
which is why the claim is required rather than assumed.

**The symptom of getting it wrong is quiet**: the person signs in and appears in the roster
with the *default* role, while their invitation sits there still saying `pending` — because
an invitation is consumed only while the assessor is being created, and by then it is too
late. The backend logs a warning naming this template every time it declines to redeem, and
the console marks such an invitation. **Get the shortcode right before anybody signs in**:
`{{user.email_verified}}`, not any of the other names it might plausibly have. Quoted or
unquoted both work — the backend reads a real boolean and the string `"true"` alike, and,
deliberately, reads `"false"` as false.

**Create the template before anyone signs in.** The `email` claim also decides the first
admin's initial role, and that decision is taken **exactly once** — see the order in
[Preparing an environment](#preparing-an-environment--order-matters).

## Roles and the first admin (ADR-0007)

`assessors.role` is the **source of truth** for authorization, and **login never changes
anyone's role** — authenticating cannot escalate privileges.

For bootstrap (an admin is needed before an admin exists to create one) there is
`ADMIN_EMAILS`: a **provisioning** allowlist, not an authorization one. It only decides the
role a **new** assessor is created with:

```bash
ADMIN_EMAILS=you@yourcompany.com,other@yourcompany.com
```

- Email on the list and the person has **never signed in** → created as `admin`.
- Email on the list but the person **already exists** as `evaluator` → **stays** `evaluator`.
- An existing `admin` you **remove** from the list → **stays** `admin`.
- No `email` claim (missing JWT template) → `evaluator`.

This is safe **because access is invite-only**: nobody can register with an admin's email
without the invitation. If you ever disable invite-only, revisit ADR-0007.

The allowlist is the default for whoever arrives **uninvited**. Everybody after the first
admin is registered by inviting them, which is where the role is decided per person.

Changing the role of someone who already exists is done from `/admin/assessors` (ADR-0050).
Two refusals are enforced, because neither is recoverable from inside the product: **nobody
changes their own role**, and **the last admin cannot be demoted**. Every grant is recorded
with its author.

`set-role` remains as **break-glass** — for a store whose console nobody can reach, which is
the bootstrap case above:

```bash
uv run python -m app.cli set-role --email you@yourcompany.com --role admin
```

It enforces neither guardrail. That is the point of a break-glass tool, and the reason not to
reach for it when a screen would do.

## When somebody leaves (ADR-0051)

Deactivate them from `/admin/assessors`. Nothing is deleted — their evaluations and the
reports naming them are what happened, and an `Assessor` is the key of provenance — but they
are offered no new work and **every request they make answers 403**. It is reversible from
the same row. The same two refusals apply: not yourself, and not the last active admin.

Deactivating does **not** cancel their open assignments; that lives in campaigns and stays a
manual step.

## Registering the evaluators after the first admin (ADR-0049)

Inviting somebody creates **no account**: it records the address, the role and the expertise
profile, and the `assessors` row still appears at that address's first login, already
carrying them. Done from `/admin/assessors` in the console, or here:

```bash
uv run python -m app.cli invite-assessor --email ada@yourcompany.com \
    --role evaluator --name "Ada Lovelace" --expertise "Instructional design"
uv run python -m app.cli list-invitations
```

An invitation is redeemable for seven days, at most one is pending per address, and re-sending
reopens a window that closed. Revoking one frees the address to be invited again.

Under `AUTH_MODE=clerk` with `CLERK_SECRET_KEY` set, this **also creates the Clerk
invitation**, so it is one act: the person gets Clerk's email and can sign in to an
invite-only instance.

The link lands on **`/accept-invitation`**, which renders a sign-up. That is not a detail:
somebody accepting an invitation **has no account yet**, so Clerk hands the ticket over as
`__clerk_status=sign_up`, and a page rendering the sign-in form cannot complete it — it
renders and spins for ever. Override with `CLERK_INVITATION_REDIRECT_URL` only towards
another page that signs somebody **up**; the default is
`<first ALLOWED_ORIGINS entry>/accept-invitation`. Point Clerk's own
`NEXT_PUBLIC_CLERK_SIGN_UP_URL` at the same route.

Under `AUTH_MODE=local`, or with no secret key, nothing is delivered and the log says so —
the invitation still stands and is redeemed at that address's first sign-in.

**The invitation is where the panel is told what happens to what they write**, because it is
the last moment before they can start. Clerk's own email is the one they receive, so the notice
goes in that template, in the Clerk dashboard, once per instance — nothing in this repository
composes it. One sentence is enough:

> Your answers and comments are read by our team alongside the other reviewers', under an
> identifier rather than your name.

The evaluator's own screen carries the short half of it (`Your answers are recorded under an
identifier, not your name`) where somebody about to answer can see it again. Keep the two
saying the same thing: if what the export shares ever widens, the sentence here is what has to
change first, and it can only change for people invited after it.

> ⚠️ **Delivery can fail without the invitation failing.** Clerk refuses an address that is
> already a Clerk user, and that rule cannot be bypassed. The invitation is created here
> either way and the answer says `delivered: false` with Clerk's own sentence; the remedies
> are **Re-send**, or inviting that person in Clerk by hand.

## Running Clerk against your own machine

Clerk's **development** instance is built for `localhost`, so the real login flow — and the
real invitation flow — can be exercised without deploying anything. Nothing in the code
prevents it: the only guard is the reverse one (`AUTH_MODE=local` refuses a remote database
and `ENVIRONMENT=production`).

`backend/.env`:

```bash
AUTH_MODE=clerk
CLERK_ISSUER=https://<your-app>.clerk.accounts.dev
CLERK_SECRET_KEY=sk_test_...
# DATABASE_URL stays the local container; ALLOWED_ORIGINS already covers localhost:3000
```

`frontend/.env.local`:

```bash
NEXT_PUBLIC_AUTH_MODE=clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
```

Then write the **JWT template** — `uv run python -m app.cli setup-clerk-jwt-template`, before
signing in for the first time. It works from here for the same reason it needs no `AUTH_MODE`:
a development instance of Clerk is a real instance, and this configures the one its secret key
names.

What changes when you do this:

- The user picker is gone; you sign in through Clerk, as a real person.
- `GET /dev/identities` and the rest of the dev-only surface answer **404**, by design.
- `seed-demo` refuses to run: it only works in local mode.
- Inviting from the console really creates a Clerk invitation and really sends an email.

The two modes share one database, and a local assessor's credential is stored as
`('local', <email>)` while a Clerk one is `('clerk', <sub>)`, so they cannot collide — the
same person signing in both ways is two assessors, which is what you want on a dev box.

## Preparing an environment — **order matters**

This sequence runs **once per environment** (one Clerk instance = one environment). The order is
not a preference: three of these steps degrade **silently** when they run late — nothing raises,
nothing an operator is watching logs, and the price is paid later in data. Two of the three are
repairable afterwards and say how below. The third stops being repairable the moment an expert
answers, because by then it has cost their answers to questions they should never have been
asked.

> ⚠️ **The JWT template with the `email` claim must exist BEFORE the admin's first login.**
> Without that claim the assessor is created as `evaluator` (a safe degrade), and since the
> allowlist applies **once, at row creation**, adding the template later does not rescue it.
> Two individually correct behaviors that, in the wrong order, leave the admin born an
> evaluator.

### 1. The store (Neon)

Create the project and keep its connection string. It needs the psycopg3 prefix and SSL:

```bash
DATABASE_URL=postgresql+psycopg://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Put it in the **same region the API runs in**: a request pays that round trip many times over
and a browser pays it once, so this is the latency that matters.

Nothing migrates it by hand. The API's **pre-deploy command** is `alembic upgrade head`
(step 2), so it runs once per deploy, before traffic switches, and the first deploy is also the
first migration. A failure there aborts the deploy and leaves the previous version serving.

### 2. The API (Render)

**Render does not build this repository.** It is private and owned by an organisation whose
GitHub Apps are not ours to install, so the service runs a **prebuilt image** that
`task deploy:api` publishes from a developer's machine (see
[Releasing](#releasing-once-it-is-running)). Publish one first — the service needs something to
point at — and then create a web service of type **Existing image**:

| Field | Value |
|---|---|
| Image URL | `IMAGE_REPO:latest`, from `backend/.env.instance` |
| Credential | a token that can read that registry — for GHCR, `read:packages` |
| Region | the one the Neon project is in |
| Instance type | any **paid** one; the pre-deploy command is not available on free |
| Health check path | `/health` |
| Pre-deploy command | `alembic upgrade head` |

And the environment:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `AUTH_MODE` | `clerk`. Declared rather than left to the code's default, so the refusal is never what discovers it: `local` here does not boot at all (ADR-0008) |
| `DATABASE_URL` | Neon, from step 1 |
| `CLERK_ISSUER` | step 4 |
| `CLERK_SECRET_KEY` | step 4 — without it an invitation is recorded here and never created in Clerk, so the person invited cannot sign in at all (ADR-0049) |
| `ADMIN_EMAILS` | provisioning, not authorization: it decides the role a **new** assessor is created with and never changes an existing one (ADR-0007) |
| `ALLOWED_ORIGINS` | step 3, and that entry goes **first** |

Two of those cannot be known yet — the Clerk keys and the console's own origin — so a first
pass with placeholders and one edit afterwards is the normal shape of this step, not a mistake.

**What is deliberately absent, and why:**

- `CLERK_JWKS_URL` — left empty it is derived from the issuer, and a value copied over from a
  local `.env` silently wins over it and points this instance at a development one.
- `LLM_API_KEY` — no assessor judges from this instance. Measuring a generator runs on a
  developer's machine, and a key on a host with no use for it is a key that can leak for
  nothing (ADR-0034 makes it access, never identity).
- `BREATHECODE_*` / `RIGOBOT_*` — the seat infrastructure of ADR-0061 is created once by hand
  and may not exist. Unset is a valid deployment: every screen works and the course loads
  without its AI, saying so.
- `LOCAL_SOURCE_ROOTS` — local trees are served only under `AUTH_MODE=local`, and a locator
  into this host would point at bytes it does not serve.

`GET /health` answering `{"status": "ok", "environment": "production"}` is what says the schema
and the store are both there: it runs a real query, so it cannot answer `ok` over a database it
cannot reach.

### 3. The console (Netlify)

Netlify does not build this repository either, for the same reason, so the site is created and
published from here:

```bash
netlify sites:create --name <the site>
netlify link
```

`netlify.toml` at the repository root declares the base directory, the build and the Node
version, and the CLI reads it exactly as the hosted build would. What the dashboard supplies is
the environment, and **all of it is read at build time**, so changing any of it needs a redeploy
rather than a restart:

```bash
NEXT_PUBLIC_API_URL=https://<the Render service>.onrender.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/accept-invitation
```

`NEXT_PUBLIC_AUTH_MODE` is left unset on purpose: anything that is not `local` is `clerk`, so a
missing or misspelled value fails safe.

Then `task deploy:console` publishes it, and `task deploy:console:preview` does the same to a
draft URL when you want to look before promoting.

Then go back to Render and set `ALLOWED_ORIGINS` to this site's URL. **It goes first**, because
the first entry is both what CORS allows and what Clerk's invitation link is derived from
(`Settings.invitation_redirect_url`) — and an invitation that lands on the wrong origin is
found by the person who cannot accept it.

### 4. Clerk — all of it before anybody signs in

1. The **JWT template**: `uv run python -m app.cli setup-clerk-jwt-template`, with
   `CLERK_SECRET_KEY` in that shell's environment
   ([what it writes and why](#clerk-adr-0004)). `email` decides who is born an admin and
   `email_verified` decides whether an invitation can be redeemed at all.
2. Invite-only, in **Restrictions**.
3. Invite the admin's account. **Nobody signs in yet.**

### 5. The first admin signs in

Now, and not before. Verify with `GET /me` that it says `"role": "admin"`.

Everything below is attributed to somebody, so this row has to exist before any of it: an act
names its author (ADR-0042), and `--email` is how it finds them.

### 6. What the store has to hold

From a checkout on **your own machine**, pointed at the deployed store — not from a shell on the
server, which has no `docs/seed/`. What points it there is `backend/.env.instance`: copy
`.env.instance.example`, fill it in, and the `instance:*` tasks read it. Values from it win over
`backend/.env`, so your local environment is left alone and the two never have to be swapped.

Each of these announces the host it is about to write to and refuses until `CONFIRM` names it
back, because they sit in the same file as `db:reset` and the two must never be confused.

```bash
CONFIRM=<the neon host> task instance:seed        # re-runnable
CONFIRM=<the neon host> task instance:generator   # once, ever
```

`instance:seed` installs the two things nothing in the app can author — the **human reference
instrument** (one Likert statement per quality, ADR-0052) and the **pedagogical reference data**,
the qualities, dimensions and frameworks an instrument cites; a campaign pins a reference
instrument when it opens (ADR-0056), so without them there is no campaign to open — and then
**accepts the extraction** for both package formats.

`instance:generator` mints the generator lineage and is deliberately not part of that chain: it
is the one act here that is not idempotent and must not be, since a lineage still takes a typed
name and a second one is a typo worth refusing rather than a repetition worth absorbing
(ADR-0031).

`seed-workbench` is **not** part of any of this. It replays acts that are human ones by decision
and refuses outside `AUTH_MODE=local` (ADR-0045); what a deployed instance needs of it, it gets
one act at a time here, attributed to the admin who performs it.

**Accepting the extraction is not paperwork, and it is the step that is paid for in data.** It
is what arms automatic profiling on registration (ADR-0029), and an item is withheld from a
human only when the profile *settles* that its datum is undeclared (ADR-0053). A course with no
profile settles nothing — so on a store where the extraction was never accepted, the four items a
`LearnpackV1` course cannot answer are **asked anyway**, of every expert, with no error and no
warning anywhere.

Accepting it **before** the courses are registered is what makes this automatic. Accepting it
afterwards profiles nothing retroactively: those courses stay unread until somebody reads them
from `/admin/profiles`. So the order is recoverable right up until an expert answers, and not
one minute after — nothing detects it then, and nobody can be asked again.

**Then the courses**, and in two ways, because the two formats are not reachable the same way:

```bash
CONFIRM=<host> task instance:courses:v1    # a spreadsheet of URLs
CONFIRM=<host> task instance:courses:v2    # a tree on this machine
CONFIRM=<host> task instance:deployments   # where each one is deployed
```

- **`LearnpackV1`, from URLs.** The locators stay public, so the deployed API can read those
  packages again by itself later.
- **`LearnpackV2`, from a local tree.** The generator's run output is served nowhere, so it is
  read off disk — and that takes **two processes**: `task backend`, the API in local mode,
  serving the tree (registering fetches one file through that mount before it writes anything),
  and the task above, writing to the deployed store. The locators that land there therefore
  point at `localhost`. For a campaign that is fine: the evaluator's screen reads the profile
  stored at registration and fetches nothing. What it costs is that the deployed API can never
  re-read those packages — `/admin/profiles` fails on them, and only there.
- **Deployments last**, because a course is usually deployed after it is registered. Until a
  course has a consumable URL it can be judged automatically but is refused by the assign picker
  (ADR-0028), so for this errand every one of them needs one.

The two commands underneath are the ordinary ones —
[Registering courses](README.md#registering-courses) and
[Declaring the deployment](README.md#declaring-the-deployment-of-a-registered-course-declare-deployment)
say what they do and what the CSVs look like.

**Before opening the campaign, read `/admin/profiles` and confirm every course was profiled.**
That screen is where a package never read says so, and where it can be read now. A failure at
registration is otherwise only in the summary line the command printed at the time, and the
cost of missing it is the paragraph above.

### 7. The campaign

From the console, both of them:

- **Invite the evaluators** from `/admin/assessors`. **That is the whole act**: with
  `CLERK_SECRET_KEY` set it creates the Clerk invitation too, so do **not** also invite them in
  Clerk by hand — Clerk refuses an address that is already one of its users, and the second
  invitation is the one that comes back `delivered: false`. They sign in → their role and
  expertise come from the invitation.
- **Open the campaign** and assign.

**If you got the order wrong** (the admin already signed in and landed as `evaluator`):
nothing to delete, no allowlist to touch — fix it with

```bash
uv run python -m app.cli set-role --email <admin email> --role admin
```

which is the break-glass path: at that point there is no admin, so there is nobody who could
grant the role from the console.

## Releasing, once it is running

**Pushing releases nothing.** Neither host watches this repository, and an image-backed service
does not redeploy when a new image appears under its tag — so a release is an act somebody
performs:

```bash
task deploy:api        # builds, publishes the image, triggers the release
task deploy:console    # builds and publishes the site
```

`deploy:api` refuses while anything tracked is uncommitted: it tags the image with the commit,
and a tag that misdescribes what is inside it outlives the chance to notice. Without a
`RENDER_DEPLOY_HOOK` it publishes and then says so — the release is *Manual Deploy* in the
dashboard.

A release of either host **never touches the store**: Neon is its own service, and nothing in a
deploy writes data. What moves with the code is the schema, and the **pre-deploy command** is
what moves it: `alembic upgrade head`, once, before traffic switches. If it fails, Render halts
the release and the previous version keeps serving — which is also why it is not in the start
command, where a half-migrated schema would meet live traffic.

The seeders are not in that path and must not be: `seed` is idempotent, but a step that reruns
on every release is a step nobody reads the output of.

**Back the store up before each release while a campaign is open**:

```bash
CONFIRM=<the neon host> task instance:dump
```

The migrations here do not destroy data, but that is a convention rather than a guarantee, and
this is thirty seconds against the only copy of what the panel answered. It writes outside the
repository, to `DUMP_DIR`, and deliberately: the dump is the **identified** record — it carries
every expert's address — and it is what the campaign's results are read from once this instance
is gone.
