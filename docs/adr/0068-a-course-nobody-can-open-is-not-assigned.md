# ADR-0068 — A course nobody can open is not assigned

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Orchestration · Evaluand Registry

## Context

ADR-0028 made `consumable_url` optional and gave it one meaning: a declared value asserts that
a deployed, human-consumable instance of this content version exists, and an absence asserts
that none does. It also decided, in clause 5, not to enforce the consequence:

> **5. The guard is advisory, not enforced.** Nothing on the server refuses the assignment.
> Enforcing it means Orchestration reading the registry inside the assignment path — a port and
> a gateway, the ADR-0006 shape — and the failure it prevents is visible, reversible and rare:
> the evaluator reads "no deployed instance" and the admin unassigns. Deferred deliberately.

Two of those three words have stopped being true.

**Reversible** was the strongest of them, and it was the weakest in practice: at the time there
was no act that could declare a URL after registration, so "the admin unassigns" was the only
repair, and re-deploying the course led nowhere. ADR-0054 built the missing act — a deployment
is declared when it exists, and redeclared when it moves. The refusal this ADR adds therefore
has somewhere to send the admin, which is exactly the property a refusal needs.

**Rare** was true of a demo and is false of a panel. The first campaign is 40 courses over 25
experts, assigned by hand; the courses it draws on are registered in bulk by the generator loop,
where declaring nothing is the *normal* case, not the exception — ADR-0028 §4 says so itself.

**Visible** was always the softest claim. What the evaluator sees is a screen saying the course
is not available; what the campaign sees is an assignment holding one of the course's seats
against the quorum, indistinguishable in every list from one that will be answered. The console
now reads assignment coverage per course, which makes the phantom seat *countable* — and
counting it is not the same as refusing it.

## Decision

**A course that declares no deployed instance is not assigned to a human. The act refuses it,
with the same status and the same shape as the rest of the assignment path's refusals.**

### 1. The registry is asked whether, not where

Orchestration takes a `ContentsGatewayPort` answering `declares_a_deployment(content_id)`. Not
the URL: what the act decides is whether there is anything to hand somebody, and the address
is the registry's to serve when the evaluator opens the assignment. The port keeps the
assignment path from acquiring an opinion about what a consumable URL looks like.

### 2. It is the second half of one question, and it sits beside the first

ADR-0067 refuses an assignment with nobody to read the course; this one refuses an assignment
with nothing to read. Same act, same place in it — after the campaign and the scope, before the
duplicate lookup, before anything is written — and the same `422`, since both are the body of a
request being unprocessable rather than a conflict with a state.

### 3. A content the store cannot resolve is out of scope, not undeployed

The campaign's scope is a **copy** of a dataset version's membership, taken when it opened
(ADR-0058 §5), so it can name a content the registry no longer holds. That is refused as
`ContentNotInCampaign` rather than as a missing deployment: the honest answer is that this
campaign cannot be about that course any more, not that somebody should go and deploy it.

### 4. Nothing already assigned is touched, and the read path stays

The rule governs the act. Assignments made before it stand, and the whole read path they
exercise — a snapshot with a null URL, an assignment detail carrying null, an evaluator screen
that states the absence instead of framing nothing (ADR-0028 §4) — is unchanged and still
tested. It is the code that keeps those rows honest, and this ADR does not create them, it
stops creating more.

### 5. `[future]` — withdrawing a deployment

ADR-0054 §5 left clearing a declaration refused and named: `consumable_url` cannot be set back
to null. So after this ADR the only way an assignment can carry a null URL is by predating the
rule. When withdrawal is built, this refusal is the reason it must decide what happens to the
assignments already made against that course — and the answer is not automatic cancellation
(ADR-0067 §6 declined the equivalent).

## Relationship with ADR-0028

**Amends clause 5 and does not supersede the ADR.** What dies is one clause: the guard is now
enforced. Everything else ADR-0028 decided stands and is realized in code — the field is
optional and http(s)-validated when declared, a serving root is not a deployment, registration
does not refuse a source that yields no URL, automated evaluation never reads the field, and the
minted rows stay corrected. ADR-0028 keeps its `accepted` status, for the reason it gave itself
when amending ADR-0027: marking it superseded would retire five live clauses to close one
deferral. Its own "deferred, doors left open" line named this as the door; this is it closing.

## Consequences

- (+) The failure ADR-0028 accepted — "a human evaluator can still be assigned a course they
  cannot open" — stops being possible, at the only gate where it could be prevented cheaply.
- (+) The refusal is repairable rather than terminal, which it would not have been before
  ADR-0054: declare the deployment, assign again.
- (+) The console's disabled option stops being the only thing standing between a bulk-registered
  population and a panel of experts.
- (−) A course deployed *after* its version was registered must have its URL declared before it
  can be assigned. That is one extra act, and it is the act that makes the declaration true.
- (−) A wrong declaration still passes: ADR-0028's `(−)` about a transport-shaped rule is
  inherited whole. An http root that only serves a package's bytes declares a "deployment" this
  gate accepts. The guard refuses silence, not a lie.
- (−) One more query in the assignment path, after the roster read ADR-0067 added. Two gateway
  calls per assignment, at a campaign's rate of assignment.

## Alternatives considered

- **Keep it advisory and rely on the console, as ADR-0028 chose.** Rejected by the Context: the
  three reasons that decision rested on have expired — repair now exists, the case is no longer
  rare, and visibility was never the same thing as prevention.
- **Refuse at campaign open, so an undeployed course never enters a scope.** Rejected by
  clause 4 and by ADR-0058: a dataset is a set of evaluands, most of which the automated path
  scores perfectly well, and a campaign's scope is copied from it. Refusing there would make
  human suitability a property of the set, which is the confusion ADR-0028 spent itself undoing.
- **Refuse at `open`, when the evaluator picks the assignment up.** Rejected: the seat is
  already taken by then, the quorum already miscounted, and the person is already in front of
  the failure. The gate belongs where the act is.
- **Return the URL through the port and let the use case judge it.** Rejected by clause 1: it
  would give Orchestration an opinion about what makes a URL consumable, which is the registry's
  invariant (ADR-0028 §1) and is validated there.
- **Warn instead of refusing — assign, and flag it.** Rejected: that is what the current
  arrangement already is, with the console as the warning. A flag nobody has to clear is read by
  nobody.

## References

ADR-0028 §5 (the amended clause), §1 and §4 (the field's meaning and why automated evaluation
does not notice — both untouched) · ADR-0054 (the act that makes this refusal repairable, and
§5's refusal to clear a declaration, which clause 5 above inherits) · ADR-0067 (the other half
of the same question, and the port-and-gateway shape both use) · ADR-0058 §5 (the scope is a
copy, which is why clause 3 exists) · ADR-0006 (the shape clause 5 of ADR-0028 predicted this
guard would take) · ARCHITECTURE.md §3 (an application layer imports no other module) ·
GLOSSARY (`ContentPackage`, `EducationalContent`).
