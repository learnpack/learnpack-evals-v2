# ADR-0049 — Registering a human evaluator is an invitation, not an account

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Identity & Access (generic)

## Context

A human `Assessor` had no act that created it. The only write path into Identity was the
login upsert (`ResolveAssessor`, ADR-0004): the row appeared the first time somebody signed
in, with the role the bootstrap allowlist gave them (ADR-0007) and nothing else. Everything a
person does around that — deciding who joins, with which role, with which expertise — happened
outside the product, in the identity provider's dashboard, and left no trace here.

Three consequences, all of them real rather than cosmetic:

1. **The console could not say who was expected.** `/admin/assessors` showed the people who
   had already signed in and told the reader to go invite the others in Clerk. A roster that
   cannot name who is missing is not a roster.
2. **`assessors.expertise` was write-only in the wrong direction.** The column exists, the
   aggregate carries it, the GLOSSARY defines a human assessor as "a concrete SME (with an
   expertise profile)" — and no code path ever wrote it, because the only path that created
   an assessor had nothing but a JWT to work from.
3. **The role was decided by an env var or by a CLI run against production.** ADR-0007 solved
   bootstrapping honestly and said so; it was never meant to be how the fourth evaluator gets
   a role.

The settled industry shape is not the one that looks obvious. An admin console does **not**
pre-create the user: it creates an **invitation**, and the account still appears at first
login (just-in-time provisioning). Membership, role and invitation are three records, not
three columns of one. What makes the flow feel like an act is that the invitation is visible,
re-sendable and revocable — not that a row named after the person exists early.

That distinction is what lets this decision coexist with ADR-0007, which explicitly rejected
"seeding an admin row by email before the first login" on the grounds that `clerk_user_id`
is unknown until then and that linking by email afterwards is a worse vector. **That refusal
stands and this does not touch it.** An invitation is not a principal: it holds no credential,
authenticates nobody, and authorizes nothing.

The vector ADR-0007 was worried about is real, and it has produced CVEs — accepting an
invitation on an **unverified** address (better-auth GHSA-fmh4-wcc4-5jm3: anybody who
pre-registered an unverified account at someone else's address could accept, read and
enumerate their invitations). Microsoft names the general form the *false identifier
anti-pattern*: treating any federated attribute other than the subject as proof of identity.

## Decision

**The act that registers a human evaluator is an `Invitation`. The `Assessor` is still born
at the first login, and that login consumes the invitation exactly once.**

1. **`Invitation` is an aggregate of Identity & Access**, holding `email`, `role`,
   `display_name`, `expertise`, `invited_by`, `status` and `expires_at`. It creates no
   `assessors` row and grants nothing by existing.
2. **Redemption happens at creation time and only there.** `ResolveAssessor` looks for a
   redeemable invitation when — and only when — it is about to create a new assessor. An
   assessor that already exists is never re-examined, so the invariant ADR-0007 protects
   (`test_login_never_changes_the_role`: authentication cannot escalate privileges) holds
   unchanged. What the login carries no say in is what it grants: an admin decided that
   before the person arrived.
3. **The address must be verified by the provider.** Redemption requires a truthy
   `email_verified` claim. When the claim is absent the JWT template is not sending it, and
   the failure mode that matters is the silent one — every invitation would sit pending while
   people signed in and got the default role — so the miss is **logged loudly, naming the
   remedy**, instead of being swallowed as "no invitation". In `AUTH_MODE=local` the adapter
   emits it as true, because there the header *is* the identity (ADR-0008).
4. **An invitation wins over the allowlist.** `ADMIN_EMAILS` stays what ADR-0007 made it: the
   creation default for whoever arrives *without* an invitation. An invitation is a
   deliberate act, taken per person and recorded with its author, so it is the more specific
   statement. Both apply at creation and never again; `assessors.role` stays the single
   source of truth.
5. **`expired` is derived from `expires_at`, never stored.** A row that reads `pending` while
   the clock says otherwise is a lie waiting for a job to come and fix it. Deriving it costs
   one comparison and is right the moment it is asked. `revoked` and `accepted` are real
   transitions and are written; expiry is not one.
6. **At most one pending invitation per address**, enforced by a partial unique index and
   refused with a 409 that names the remedy before the index is reached. Two pending
   invitations would be two roles competing for the same first login. Accepting or revoking
   frees the address again, which is why the index is partial.
7. **Redemption is not idempotent.** A second redemption would mean two credentials answered
   to one invitation, and the second has no claim on what it was granting.
8. **Delivery is a port with a do-nothing adapter.** `InvitationDispatcherPort` exists and
   `LoggingInvitationDispatcher` writes a line saying an invitation is waiting. Creating the
   invitation in the identity provider is the provider's business and lands as its own
   adapter; putting that call inside the use case would make the act untestable without a
   network. **Until that adapter exists, inviting here and inviting in Clerk are two acts**,
   and both the console and the log say so rather than implying an email went out.

## Consequences

- (+) The roster answers "who are we waiting for", and the answer is actionable: re-send,
  revoke, or see that it expired.
- (+) `expertise` finally has a writer, at the only moment somebody knows it.
- (+) The act is auditable: `AssessorInvited`, `InvitationResent`, `InvitationRevoked` and
  `InvitationAccepted` are outbox rows carrying who did it and when (ADR-0003).
- (+) Identity gains its first events, which is consistent: a login is a fact about a session,
  inviting somebody is a fact about the roster.
- (−) Two acts instead of one until the provider adapter lands. Named, not hidden.
- (−) A provider whose JWT template omits `email_verified` silently grants the default role
  instead of the invited one. Mitigated by the warning and by the console showing how long an
  invitation has been pending; a person can still be corrected afterwards.
- (−) The invitation carries an email address in an outbox row. Consistent with `assessors`,
  which already stores it.

## Alternatives considered

- **A token and an acceptance page** (invitation link → `/accept?token=…` → bound to the
  current subject). Immune to unverified addresses and the more robust pattern in the
  abstract — rejected **for now**: it needs a public endpoint and a screen, and it only pays
  for itself once a link can actually be delivered from here, which is the adapter this ADR
  defers. Nothing in this decision closes that door: adding a token later is a column and a
  second redemption path, and the aggregate is already the thing that would hold it.
- **Matching by email without requiring verification**, leaning on invite-only the way
  ADR-0007 does → rejected: ADR-0007 documented that dependency and the condition under which
  it must be revisited, and this would add a second thing resting on the same bet, for no
  gain over asking the provider a question it already answers.
- **Pre-creating the `assessors` row and linking it at first login** → rejected, again: it is
  the alternative ADR-0007 rejected, and the CVE above is what it looks like in the field.
- **Extending `ADMIN_EMAILS` into a general roster env var** → rejected: a redeploy is not an
  admin act, an env var records no author, and it would make the role's source of truth two
  things again.

## References

- Amends the operational reading of **ADR-0007** (the allowlist is now the default for
  *uninvited* arrivals) without changing any of its clauses. **ADR-0004** (invite-only Clerk)
  and **ADR-0008** (local mode) are unchanged.
- ADR-0003 (outbox), ADR-0016 (the two kinds of assessor: only `human` is invitable — an
  automated assessor has no credential to arrive with).
