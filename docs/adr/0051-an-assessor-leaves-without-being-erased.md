# ADR-0051 — An assessor leaves without being erased

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Identity & Access (generic)

## Context

Nothing in this system ever removed a person from the roster. An `Assessor` appeared at
their first login (ADR-0004) and stayed for ever: in the assign picker, in every list, and
— the part that matters — able to sign in. Just-in-time provisioning is the arrival half of
a lifecycle and the industry names the other half as its known limit: JIT does not handle
updates or deprovisioning, because nobody stops existing by not signing in.

The gap became concrete with ADR-0049. Registering an evaluator is now an act somebody
takes deliberately, per person, with a role and an expertise profile attached. A roster you
can add to and never subtract from is not a roster; it is an append-only list that grows
until the picker is unusable, and every name on it still has a working credential.

Deleting the row is not the alternative, and this repo has already made the argument once.
ADR-0033 refused to retire registered content because a published `StudyReport` freezes what
it evaluated, and a dangling reference inside a document that by design cannot be corrected
breaks the reproducibility promise. An `Assessor` is a stronger case: it is **the key of
provenance and of calibration** (GLOSSARY), it is one third of the triple that identifies a
study's result (ADR-0042), and every `CriterionScore` names its author. A person leaving the
project does not unmake what they judged.

## Decision

**Leaving is a state on the aggregate, and it withdraws the future while leaving the record
alone.**

1. **`assessors.status ∈ {active, deactivated}`**, NOT NULL, default `active`. Unlike
   migration 0021's deliberate absence of a default, a null would carry no meaning here:
   every assessor that exists takes part, and a forgotten column means the ordinary case
   rather than a silent guess.
2. **Deactivating deletes nothing.** Evaluations, assignments, judgments and the reports
   naming them are untouched, because they record what happened. The row itself stays, so
   every id that points at it still resolves.
3. **A deactivated assessor does not get through the door.** The refusal lives in
   `get_current_assessor` — the one place a request becomes an identity — rather than in
   each handler, so no surface can be the one that forgot. A status that only removed
   somebody from pickers would be cosmetic: their credential would still open everything.
4. **Two guardrails, the same two as ADR-0050, for the same reason** (neither failure has an
   undo inside the product): **you cannot deactivate yourself**, and **the last active admin
   cannot be deactivated**.
5. **A deactivated admin does not count as an admin.** `count_admins()` counts active ones —
   otherwise the guard would protect a door nobody can open, since somebody who left is not
   somebody who can grant a role back. This also makes ADR-0050's guard read correctly:
   demoting the last *active* admin is what it refuses.
6. **An automated assessor is out of scope.** It is withdrawn by ceasing to declare it in
   code; what it may do is ratification's answer (ADR-0019), and a status control here would
   offer a competing one. Refused, not hidden.
7. **Setting the state somebody is already in is a no-op, not an event** — ADR-0050 §3's
   rule, applied to the second act that has the same shape.
8. **Reversible, and recorded.** `AssessorDeactivated` / `AssessorReactivated` carry
   `changedBy`. Coming back restores nothing, because nothing was taken away.
9. **Pickers drop them; the roster shows them.** In the assign form a deactivated person is
   removed outright rather than disabled-with-a-reason (the ADR-0028 idiom used for courses
   with no consumable URL): there the disabled option explains a fixable fact, here there is
   nothing to explain and nothing to fix. The assessors page keeps the row, dimmed and
   labelled, because "who used to be here" is a question that page exists to answer.

## Consequences

- (+) Offboarding exists, and it is real: no new work and no way in.
- (+) Reports, judgments and calibration history stay intact and attributable.
- (+) The assign picker stops accumulating people who left.
- (−) One more state every human-facing list has to read. Published on `AssessorResponse` so
  a caller decides how to show it, rather than being filtered server-side where a silently
  shortened list reads as a bug.
- (−) An admin can deactivate every other admin one at a time and then be unable to
  deactivate themselves. The console stays reachable, which is the property being protected;
  `app.cli set-role` remains the break-glass exit (ADR-0050 §6).
- (−) The last-admin guard reads the whole store, so it is tested at the use-case level over
  a fake repository rather than through the API, exactly as ADR-0050's is.
- (−) A deactivated person with an open assignment keeps it, unanswered. Cancelling
  assignments on departure is an orchestration act with its own aggregate (ADR-0002), and
  quietly cancelling somebody's work from an identity act would cross a module boundary in
  the wrong direction. Left as a manual step.

## Alternatives considered

- **Delete the assessor row** → rejected: it is the key of provenance (ADR-0042), and the
  same argument ADR-0033 made for content applies with more force here.
- **Filter deactivated assessors out of `GET /admin/assessors`** → rejected: a list that
  silently shrinks cannot answer "what happened to them", and every caller would then need a
  second endpoint to find out.
- **Deactivate by removing the credential** (blank `clerk_user_id`) → rejected: it destroys
  the very fact needed to let them back in, and it would collide with the aggregate's own
  invariant that a human has one.
- **Rely on the identity provider** (delete them in Clerk) → rejected: it leaves our roster
  and our authorization saying they are still here, which is the two-sources-of-truth
  problem ADR-0007 refused to create.
