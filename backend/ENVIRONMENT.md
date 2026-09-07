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

Clerk's default session token **carries neither email nor name**. Create a **JWT template**
in the Clerk dashboard with these claims:

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

Then create the **JWT template** in the Clerk dashboard, with the three claims above
(`email`, `name`, `email_verified`) — before signing in for the first time.

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

Nothing migrates it by hand. `render.yaml` declares `alembic upgrade head` as the API's
pre-deploy command, so it runs once per deploy, before traffic switches, and the first deploy
is also the first migration. A failure there aborts the deploy and leaves the previous version
serving.

### 2. The API (Render)

Apply the Blueprint from `render.yaml` at the repository root. It asks for the five values it
deliberately does not carry: `DATABASE_URL`, `CLERK_ISSUER`, `CLERK_SECRET_KEY`, `ADMIN_EMAILS`
and `ALLOWED_ORIGINS`.

Two of them cannot be known yet — the Clerk keys and the console's own origin — so a first pass
with placeholders and one edit afterwards is the normal shape of this step, not a mistake.

`GET /health` answering `{"status": "ok", "environment": "production"}` is what says the schema
and the store are both there: it runs a real query, so it cannot answer `ok` over a database it
cannot reach.

### 3. The console (Netlify)

`netlify.toml` at the repository root already declares the base directory, the build and the
Node version. What the dashboard supplies is the environment, and **all of it is read at build
time**, so changing any of it needs a redeploy rather than a restart:

```bash
NEXT_PUBLIC_API_URL=https://<the Render service>.onrender.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_CLERK_JWT_TEMPLATE=learnpack-evals
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/accept-invitation
```

`NEXT_PUBLIC_AUTH_MODE` is left unset on purpose: anything that is not `local` is `clerk`, so a
missing or misspelled value fails safe.

Then go back to Render and set `ALLOWED_ORIGINS` to this site's URL. **It goes first**, because
the first entry is both what CORS allows and what Clerk's invitation link is derived from
(`Settings.invitation_redirect_url`) — and an invitation that lands on the wrong origin is
found by the person who cannot accept it.

### 4. Clerk — all of it before anybody signs in

1. The **JWT template** with [all three claims](#clerk-adr-0004). `email` decides who is born
   an admin, `email_verified` decides whether an invitation can be redeemed at all, and a
   template written once is written right.
2. Invite-only, in **Restrictions**.
3. Invite the admin's account. **Nobody signs in yet.**

### 5. The two things nothing in the app can author

From a checkout, pointed at Neon — not from a shell on the server, which has no `docs/seed/`.
Set `DATABASE_URL` and `AUTH_MODE=clerk` **in that shell's environment**, which takes precedence
over `backend/.env` and so needs no edit to your local one, and then:

```bash
uv run python -m app.cli seed
```

That installs the **human reference instrument** (one Likert statement per quality, ADR-0052)
and the **pedagogical reference data** — the qualities, dimensions and frameworks an instrument
cites. A campaign pins a reference instrument when it opens (ADR-0056), so without this there
is no campaign to open.

`seed-workbench` is **not** part of this. It replays acts that are human ones by decision and
refuses outside `AUTH_MODE=local` (ADR-0045); what a deployed instance needs of it, it gets one
act at a time in step 7, attributed to the admin who performs it.

### 6. The first admin signs in

Now, and not before. Verify with `GET /me` that it says `"role": "admin"`.

### 7. What the campaign is measured on

Same shell as step 5. Accepting an extraction is a human act and names its author, which is why
step 6 comes first: the row has to exist for `--email` to find it. Registering the lineage names
nobody — it mints a name that nothing ever renames (ADR-0031), so it is typed once and reviewed
rather than attributed.

```bash
uv run python -m app.cli accept-extraction --package-format LearnpackV1 --email <admin>
uv run python -m app.cli accept-extraction --package-format LearnpackV2 --email <admin>
uv run python -m app.cli register-generator --name learnpack-generator
```

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

Then the courses and where they are deployed — see
[Registering courses](README.md#registering-courses) and
[Declaring the deployment](README.md#declaring-the-deployment-of-a-registered-course-declare-deployment).
A course with no consumable URL can be judged automatically but is refused by the assign picker
(ADR-0028), so for this errand every course needs one.

**Before opening the campaign, read `/admin/profiles` and confirm every course was profiled.**
That screen is where a package never read says so, and where it can be read now. A failure at
registration is otherwise only in the summary line the command printed at the time, and the
cost of missing it is the paragraph above.

### 8. The campaign

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

## Redeploying, once it is running

A redeploy of either host **never touches the store**: Neon is its own service, and nothing in
a deploy writes data. Pushing to the tracked branch is the whole act.

What moves with the code is the schema, and `render.yaml`'s pre-deploy command is what moves
it: `alembic upgrade head`, once, after the build and before traffic switches. If it fails,
Render halts the deploy and the previous version keeps serving — which is also why it is not in
the start command, where a half-migrated schema would meet live traffic.

The seeders are not in that path and must not be: `seed` is idempotent, but a step that reruns
on every deploy is a step nobody reads the output of.

**Take a `pg_dump` before each redeploy while a campaign is open.** The migrations here do not
destroy data, but that is a convention rather than a guarantee, and it is thirty seconds
against the only copy of what the panel answered.
