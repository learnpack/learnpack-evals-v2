# ADR-0050 — Granting a role is an act of the console, with guardrails

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Identity & Access (generic)
**Supersedes:** clause 3 of ADR-0007 (`app.cli set-role` as the *only* mechanism).

## Context

ADR-0007 settled a real security property and wrote a test for it:
`test_login_never_changes_the_role` — **authenticating cannot escalate a privilege**. To
keep it obviously true, it also made `app.cli set-role` the only way to change a role after
creation, and the console said so on screen: *"Roles are changed with `app.cli set-role`,
never from a screen: a login must not be able to escalate a privilege."*

That sentence conflates two different actors. The invariant is about **the person signing
in**; the CLI restriction is about **the person administering**. Nothing in the first
requires the second. What it does require is that whoever grants a role has already been
authorized to do it and that the act is recorded.

The cost of the conflation is not theoretical. Changing one person's role means SSH or a
local checkout, credentials for the production database, and a command run by whoever has
them — so in practice it is one person, at a time that suits them, with no record beyond
shell history. ADR-0049 has just made the *first* role a per-person decision taken in the
console; leaving every subsequent one in the CLI would mean the roster is editable exactly
once.

The industry shape is uncontroversial — an admin console with a role control, plus two
guardrails that every large platform enforces because both failures are unrecoverable from
inside the product:

- **The last admin cannot be demoted.** Azure returns `CannotDeleteLastRbacAdminAssignment`;
  Google Workspace and the rest have the equivalent. Losing it locks the console for
  everybody, and there is no screen left that could undo it.
- **Nobody changes their own role.** It is how the first failure happens in one click while
  somebody means to tidy a list.

## Decision

**An admin grants and withdraws roles from the console. `assessors.role` stays the single
source of truth, and the act is refused in the two cases that cannot be undone from inside.**

1. **`PATCH /admin/assessors/{id}`**, admin-only, taking the target role. It is not a login
   path: the caller is already authorized, and the act names its author.
2. **Three typed refusals**, all 409 except the first:
   - `AssessorNotFound` → 404.
   - `CannotChangeOwnRole` — somebody else grants you a role.
   - `CannotDemoteLastAdmin` — counted in the store at the moment of the act, not over a
     list a page load once read.
   - `NotAHumanAssessor` — an automated assessor has no role to grant; what it may do is
     decided by ratification against an instrument version (ADR-0019), and offering a role
     control for one would suggest a second, competing answer.
3. **Setting the role somebody already has is a no-op, not an event.** Reporting a role
   change that changed no role would put a fact in the outbox that never occurred.
4. **`AssessorRoleChanged` carries `from`, `to` and `changedBy`.** The audit question is
   never "what is their role" — the table answers that — but "what changed, and who decided
   it".
5. **The invariant of ADR-0007 is unchanged and still tested.** No login path reads or writes
   a role for an assessor that already exists; ADR-0049 §2 keeps redemption confined to
   creation for the same reason.
6. **`app.cli set-role` stays, as break-glass**, and is documented as such: it is what fixes
   a store whose console nobody can reach — the bootstrap case ADR-0007 was written for, and
   the last-admin case this ADR refuses to create.

## Consequences

- (+) The roster is editable by the people who own it, without a production database
  credential.
- (+) Every grant leaves an outbox row naming its author (ADR-0003). The CLI never did.
- (+) The two lockout failures become impossible through the console instead of being
  possible and merely unlikely.
- (−) One more admin-only write surface. Mitigated by it being the narrowest possible one:
  one field, one aggregate, three refusals.
- (−) The last-admin guard reads the whole store, so it cannot be exercised honestly by an
  integration test against a shared database. It is tested at the use-case level over a fake
  repository, and that split is deliberate rather than a gap.
- (−) An admin can still demote every *other* admin one at a time and then be unable to
  demote themselves. That leaves the console reachable, which is the property being
  protected; the CLI remains for the rest.

## Alternatives considered

- **Keep the CLI as the only path** (status quo) → rejected: it makes the roster editable
  once, by whoever holds production credentials, with no record.
- **Roles in the identity provider** (Clerk metadata / app roles in the token) → rejected:
  it would give `assessors.role` a competitor, which is exactly what ADR-0007 refused to
  create. Reconsider only if roles ever have to be governed from a customer's directory,
  which is not this product.
- **A confirmation-only guard for the last admin** (warn, allow) → rejected: warnings are for
  facts a person can act on afterwards. This one has no afterwards.
- **Allowing self-demotion when another admin exists** → rejected as an unnecessary special
  case: the rule "somebody else grants it" is one sentence, and asking a colleague costs a
  message.

## References

- Supersedes **ADR-0007 clause 3**; the rest of ADR-0007 (the provisioning allowlist and its
  invite-only dependency) is untouched.
- **ADR-0049** (an invitation decides the *first* role, for people who do not exist yet).
- **ADR-0016**/**ADR-0019** (why an automated assessor has no role).
