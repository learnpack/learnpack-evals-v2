# ADR-0007 — First-admin bootstrap: provisioning allowlist

**Status:** accepted · **clause 3 superseded by ADR-0050** · **Date:** 2026-07 ·
**Context:** Identity & Access (generic)

## Context
The role lives in `assessors.role` (our DB), not in Clerk (ADR-0004). The MVP needs at least
one **admin** account (register courses, open a campaign) and one **evaluator** before the demo.

The only existing mechanism (`app.cli set-role`, block 2) has a bootstrapping problem: it requires
that the person **has already logged in** *and* that someone run a CLI **against the production
DB**. For a deploy on Render that is real friction.

The constraint to respect: block 2 left a tested invariant —
`test_login_never_changes_the_role`, "authentication must not be able to escalate privileges".
Applying an allowlist on **every** login would break it, and would leave two sources of truth for the
role (does removing someone from the list demote them on the next login?).

## Decision
**`ADMIN_EMAILS` is a *provisioning* allowlist, not an authorization one.** It is applied
**only when creating** the `Assessor` (first login) and never again.

| Situation | Result |
|---|---|
| Email on the list, assessor **does not exist** | created with `role='admin'` |
| Email on the list, assessor **already exists** as `evaluator` | **stays** `evaluator` |
| Existing `admin` assessor is **removed** from the list | **stays** `admin` |
| No `email` claim (JWT template missing) | `evaluator` — degrades safely |

Design consequences:
1. **`assessors.role` remains the single source of truth** once the row is created. The env
   var behaves like a *creation default*, analogous to a seed — not like a permission.
2. **The invariant holds:** logging in never changes anyone's role.
3. **`app.cli set-role` remains the only way to change a role** after creation.
4. Case-insensitive matching with trim.

**Explicit security dependency:** this is safe **because access is invite-only**
(ADR-0004): nobody can sign up with an admin's email without the invitation. If invite-only is ever
disabled, this allowlist becomes an escalation vector and **this decision must be
revisited**. It is noted in the docstring of `ResolveAssessor._initial_role`.

## Consequences
- (+) Solves the bootstrap without a CLI against production: set `ADMIN_EMAILS` on Render and the
  owner's first login is already admin.
- (+) Introduces no second source of truth and does not break the no-escalation invariant.
- (+) Zero schema changes; the rest of the system is unaware.
- (−) The initial role depends on an env var: changing it requires a redeploy. Acceptable, because it
  only affects **accounts that do not exist yet**.
- (−) An admin created by mistake must be demoted with `set-role` (removing them from the list is not enough)
  — which is exactly the correct behavior.

## Alternatives considered
- **Allowlist applied on every login** (initial proposal) → rejected: breaks
  `test_login_never_changes_the_role` and duplicates the role's source of truth.
- **Only `set-role` (status quo)** → rejected for the demo: requires a prior login + a CLI against the
  production DB. Kept as the role-change mechanism.
- **Seeding an admin row by email before the first login** → rejected: `clerk_user_id` is
  `unique NOT NULL` and is unknown until the first login; it would force a linking by email, which
  is a worse vector.

## Implementation
`ADMIN_EMAILS` (CSV) → `Settings.bootstrap_admin_emails` → injected into `ResolveAssessor`
from `platform/security.py`. The rule lives in `ResolveAssessor._initial_role`.
Tests: `backend/tests/test_admin_bootstrap.py` (9 cases, including the two for no-escalation and
no-demotion).
