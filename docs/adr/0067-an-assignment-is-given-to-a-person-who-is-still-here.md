# ADR-0067 — An assignment is given to a person who is still here

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Orchestration · Identity

## Context

An assignment is the door humans come in through. ADR-0016 §1 draws the line that way and
nowhere else: "humans enter through assignments/UI/asynchrony; automated ones through config +
execution". Two kinds of assessor, two doors, and the difference is structural rather than a
matter of degree.

The store does not say so. An automated assessor is registered with a name, a version and a
`source_config`, and nothing else — so it takes the defaults every assessor takes, `evaluator`
and `active`, because those defaults were written for the only kind that existed when the
aggregate was. Every instrument package in the store is therefore, as far as any query can tell,
an active evaluator. The console listed them beside the experts in the assign picker until the
predicate there was corrected to ask about `kind` as well; the act itself accepted them before
that fix and accepts them still.

The same hole swallows somebody who left. ADR-0051 decided that deactivating is real
offboarding — its first consequence reads "(+) Offboarding exists, and it is real: no new work
and no way in" — and realized the "no new work" half in clause 9, which drops them from the
picker. A picker is not a gate. `POST /admin/campaigns/{id}/assignments` never asked, so the
sentence was true of the console and false of the system.

What both holes produce is the same object: an assignment that will never be answered, holding
one of the course's seats against the campaign's quorum, invisible until somebody reads the
per-course coverage and wonders why a course with two evaluators has no submissions. It is
cheap to make by hand — and the first real panel is 40 courses over 25 experts, assigned one
at a time by a person with a list.

## Decision

**A course is assigned only to somebody the store can resolve, who is a person, and who is
still active. The act refuses the other three cases before it writes anything.**

### 1. The refusal lives in the act, not in the screen that offers it

The console keeps its filter, and the server stops depending on it. A guard that exists only in
the client is a guard against misclicks, not against the API — and the API is what a seeding
script, a future bulk assignment and every second client will use.

### 2. An unresolvable id is refused apart from an unusable one

`assessors` belongs to Identity, so no foreign key says the id exists — the same hole
ADR-0058 §5 left for the dataset version, filled the same way and refused with its own name.
"Nobody by that id" and "somebody who cannot be asked" are different mistakes: the first is a
bad reference, the second is a decision about a real person or a real artifact.

### 3. The role is deliberately not part of the rule

An assessor holds exactly one role (ADR-0050), so requiring `evaluator` here would mean an admin
cannot answer an instrument without ceasing to be an admin — giving up the console to pilot the
thing the console exists to run. The act refuses what is **impossible**: an artifact cannot read
a course, and somebody who cannot sign in cannot open one. Which people you would normally ask
is a *criterion*, it belongs to whoever composes the panel, and the console goes on applying it
in the picker — where a criterion can be relaxed by unticking something, which is what
distinguishes it from a rule.

### 4. Both refusals are `422`, and the automated one is not a `409`

Identity refuses its own acts on an automated assessor with `409 Conflict` (`NotAHumanAssessor`,
raised by deactivation, role change and expertise). This act refuses with `422`, beside
`ContentNotInCampaign`: there, the conflict is with a state the caller could reach — an
assessor's row exists and the act is wrong *for it*; here the id arrives in the body of a request
whose other half is fine, and the answer is that this body cannot be processed. The status codes
of this endpoint already read that way — `404` is the campaign in the path, `409` is the
duplicate, `422` is everything the body got wrong.

### 5. Orchestration asks through a port, and Identity's words stop at the gateway

The application layer imports no other module (ARCHITECTURE.md §3, executable). So the use case
takes an `AssessorsGatewayPort` returning a local `Assessee`, and the adapter over
`IdentityQueries` translates. `Assessee` carries two booleans — `is_human`, `is_active` — and
not `kind`, `role` and `status`: Orchestration is not asking what somebody is, it is asking
whether there is anybody there to read a course. Dropping the role at the boundary is clause 3
made structural, so a later reader cannot quietly start branching on it.

### 6. Nothing already assigned is touched

The rule governs the act. Assignments created before it stand, are read as they were, and are
undone the way anything else is — cancelled from the campaign view. Retroactively cancelling
somebody's work from a rule change is a decision this ADR is not making, and ADR-0051's own
`(−)` already accepted the equivalent: a deactivated person keeps the assignment they hold.

## Consequences

- (+) ADR-0051's "no new work and no way in" becomes true of the system rather than of one
  screen, and ADR-0016's two doors are actually two doors.
- (+) The failure it prevents is the expensive kind: silent, quorum-holding, and discovered
  weeks later when the campaign will not close.
- (+) The console's filter stops being load-bearing, so the next client — a script, a bulk
  assignment, a second console — inherits the guarantee instead of having to re-derive it.
- (−) One more round trip in the assignment path: the gateway reads the roster before the
  duplicate lookup. At a campaign's rate of assignment this is not a cost, it is a query.
- (−) The rule and the picker now disagree on purpose (clause 3), and a reader who assumes the
  console shows exactly what the API accepts will be surprised by an admin being assignable.
  Written down here because the disagreement is the decision, not an oversight.
- (−) An automated assessor is still an `evaluator` and still `active` in the store. This ADR
  refuses to *act* on that, it does not correct it; the defaults stay wrong for a kind they were
  never written for, and any new query over roles inherits the same trap.

## Alternatives considered

- **Give automated assessors their own role, or none.** Rejected by clause 5: it fixes the
  symptom in Identity's aggregate, needs a migration over every existing row, and leaves the
  assignment path still trusting a field instead of asking a question. The role is the wrong
  axis for this — that is what ADR-0016 decided.
- **Refuse in Identity, by making the assignment an act it authorizes.** Rejected: no module
  commands another (ARCHITECTURE.md §4), and the question "may this course be given to them" is
  Orchestration's, asked of Identity's facts.
- **Require the `evaluator` role too, so the server matches the picker exactly.** Rejected by
  clause 3: one role per assessor means it locks the admin out of their own instrument, and it
  promotes a criterion to a rule.
- **Leave it advisory and let the console be the gate, as ADR-0028 §5 chose for deployment.**
  Rejected: that reasoning turned on the failure being visible and rare. This one is neither —
  an assignment to a package looks exactly like an assignment to a person in every list, and the
  panel about to be assigned is large enough that one slip is likely.
- **Check at `open` instead, when the evaluator picks the course up.** Rejected: nobody would
  ever open it, so the check would never run. The wrong assignment has already cost a seat by
  then.

## References

ADR-0016 §1 (two kinds, two doors — the rule this enforces) · ADR-0051 §9 and its first
consequence (the picker drops them; this is what makes the claim true) · ADR-0050 (one role per
assessor, and roles as an act of the console — why clause 3 goes the way it does) · ADR-0058 §5
(`UnknownDatasetVersion`, the same missing foreign key filled the same way) · ADR-0028 §5 (the
advisory guard whose reasoning clause 4 of the alternatives distinguishes; enforced separately
by ADR-0068) · ADR-0002/ADR-0005 (the assignment aggregate and the duplicate rule this gate runs
before) · ARCHITECTURE.md §3 (an application layer imports no other module; a use case that needs
a foreign fact gets a port and a gateway) · GLOSSARY (`Assessor`, the Source axis).
