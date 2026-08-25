# Deploying an instance: identity and roles

This is for one errand: **a human evaluation campaign**, where subject-matter experts who do
not have this repository open a course in a browser and score it. That needs real accounts, so
it needs Clerk — and everything here is done **once per instance, before anyone signs in**: the
Clerk instance itself, who is born an admin, how the evaluators are registered, and the order
all of it has to happen in.

Measuring a generator's output needs none of it. That runs on your machine in
[local mode](README.md#local-mode-and-clerk-mode-adr-0008), which replaces where identity comes
from and nothing else — so the campaign flow can be rehearsed locally first, and
[Running Clerk against your own machine](#running-clerk-against-your-own-machine) is how to
rehearse the sign-in and invitation halves too.

One Clerk instance is one instance. Commands are run from `backend/`.

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

This sequence runs **once per environment** (one Clerk instance = one environment), before
anyone signs in.

> ⚠️ **The JWT template with the `email` claim must exist BEFORE the admin's first login.**
> Without that claim the assessor is created as `evaluator` (a safe degrade), and since the
> allowlist applies **once, at row creation**, adding the template later does not rescue it.
> Two individually correct behaviors that, in the wrong order, leave the admin born an
> evaluator.

1. **Render:** `ADMIN_EMAILS=<the admin's email>` (and wait for the redeploy to finish).
2. **Clerk:** create the **JWT template** with the `email` claim (above) and invite both
   accounts. **Nobody signs in yet.**
3. **Only now:** the admin signs in. Verify with `GET /me` that it says `"role": "admin"`.
4. The admin invites the evaluators from `/admin/assessors` (and, until that adapter exists,
   in Clerk too). They sign in → their role and expertise come from the invitation.
5. Register the generator and its courses (see [Registering courses](README.md#registering-courses))
   and open the campaign from the admin UI.

**If you got the order wrong** (the admin already signed in and landed as `evaluator`):
nothing to delete, no allowlist to touch — fix it with

```bash
uv run python -m app.cli set-role --email <admin email> --role admin
```

which is the break-glass path: at that point there is no admin, so there is nobody who could
grant the role from the console.
