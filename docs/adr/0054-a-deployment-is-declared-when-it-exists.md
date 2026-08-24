# ADR-0054 — A deployment is declared when it exists, and redeclared when it moves

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

ADR-0028 made `consumable_url` an optional declaration that a deployed, human-consumable
instance of a content version exists, and wrote down what it costs: *"deploying an
already-registered course means declaring a new version or a hand-written UPDATE."* The demand
was not there — the courses the genetic-algorithm loop registers are not deployed at all, and
the ones that are declare their URL at registration.

**ADR-0052 §6 created that demand.** The first reference campaign judges the deployed,
processed course while the evaluand stays the **draft** — one `contentId`, so a human
judgement and an automated one meet with no join between them. The drafts are registered from
`courses/` and, since ADR-0028, that path declares no URL: `register-package --all` refuses
`--consumable-url` outright, because one URL cannot declare a deployment for many. The
deployment happens afterwards, and nothing can attach it: `RegisterContentVersion` is the only
writer of `contents`, the registry router has no `PATCH`, and re-registering the same package
is a reported no-op. Without a URL the console disables the content in the assign picker, so
**every content the campaign means to put in front of an expert is unassignable.**

`STATUS.md` sketched the act as `attribute-generator`'s: *"one-way, actor and time recorded,
refusing what is already declared."* That sketch is what this decision revisits.

## Decision

**Declaring the deployment of a registered content is its own act, it may be repeated, and
every change is recorded.**

1. **The act exists at both gates** — `POST /admin/contents/{id}/consumable-url` and a CLI
   command — beside `POST /{id}/generator`, which is the same shape of thing: a field that
   could not be known at registration, declared later by an admin whose name is kept.

2. **It is redeclarable, and this is where it parts from ADR-0024.** Attribution is one-way
   because a generator link is a **discovery**: the fact was always true and is merely learnt
   late, so replacing one would be overwriting history. A deployment is not that kind of fact.
   It is a statement about the world **right now** — a course moves, comes down, is redeployed
   at another host — and a declaration that could be made only once would leave a dead link
   with no repair, which is the hole this ADR is closing, recreated one level up. The
   `STATUS.md` sketch inherited the one-way rule from the wrong precedent; the resemblance is
   in the shape of the act, not in the nature of what it records.

3. **A change is recorded; a no-op is not.** `ConsumableUrlDeclared` carries `from`, `to` and
   `declaredBy`, because the audit question is never *what is this content's URL* — the row
   answers that — but *what changed, and who decided* (ADR-0050's rule for the same reason).
   Declaring the URL a content already has changes nothing and **emits no event**: an entry in
   the outbox that records no change is noise a future reader has to rule out.

4. **The previous value is part of the write.** The update is conditional on it
   (`WHERE consumable_url IS NOT DISTINCT FROM :previous`), the same trick ADR-0024's
   `WHERE ... IS NULL` plays: the aggregate states the rule where it is read, the database
   holds it under concurrency, and two admins declaring at once end with one refusal instead
   of one silent overwrite.

5. **Clearing is refused, and named rather than left silent.** A course taken down is a real
   thing to want to say, and `null` already has a meaning in this column — *none declared*.
   Making the act able to write it needs an answer to what happens to the evaluations that
   were already produced against it, and nothing consumes such an answer yet. Refused for now
   and written here so the next reader knows it was a decision (the posture ADR-0020 took with
   `enum` and `levels`).

6. **What the act does not do, because the question will be asked.** It writes one column and
   two record-keeping ones. **It fetches nothing**: a `ContentProfile` is built from artifact
   locators and `content_profiling` never reads this field (ADR-0028 §4); the only subscriber
   to a registry event is auto-profiling, which reacts to `ContentVersionRegistered`; and that
   use case refuses coordinates it has already profiled, so even a replay could not re-extract.
   The evaluand's identity, its `content_hash` and its declared surface are untouched — this
   field was never one of the bytes (ADR-0017).

7. **Resolution by slug at the CLI, refusing ambiguity.** The batch takes
   `external_id,url`, because what arrives is a spreadsheet of courses and deployments and
   nobody types UUIDs. `(package_format, external_id)` is the logical content (ADR-0005), so a
   slug matching more than one registered version is **refused by name**, never resolved by
   picking one.

8. **ADR-0028 §5 is untouched.** The guard that would make the server refuse an assignment to
   an undeclared content stays advisory and stays deferred. This ADR removes the reason the
   guard would have fired, not the guard.

## Consequences

- (+) The campaign is unblocked: a draft registered from `courses/` and profiled can be
  pointed at its deployment without touching its identity, so the human and automated
  judgements still meet on one `contentId` (ADR-0052 §6).
- (+) A deployment that moves has a repair, and the record says what it moved from and who
  moved it.
- (−) **A URL can now change under an evaluation that was already submitted.** The evaluand is
  the draft and its bytes are immutable, so nothing about the judgement is rewritten — but a
  reader re-opening the link later may not see what the rater saw. The event is what makes
  that reconstructible, and it is the reason clause 3 records `from` rather than only `to`.
- (−) One more writer of `contents`, in a module whose single-writer simplicity was worth
  something. It is confined to one column and its two record-keeping neighbours.
- (−) The CLI grows a fourth way of naming a course — by slug — beside `--source`, `--all` and
  `--from-csv`'s URLs. Ambiguity is refused rather than resolved, which is the mitigation and
  also a way for a run to stop halfway.

## Alternatives considered

- **One-way, as `STATUS.md` sketched it.** Rejected on clause 2: the precedent's reason does
  not transfer, and the sketch would leave a moved deployment unrepairable.
- **A general `PATCH /admin/contents/{id}`.** Rejected: it turns a registry of declarations
  into an editable table, and the fields around this one — `external_id`, `package_format`,
  `content_hash` — are exactly the ones that must not move. A named act says what may change.
- **Declaring a new `ContentVersion` for the deployed course.** The workaround ADR-0028
  recorded, and the reason it fails here: a new version is a different `contentId`, so the
  automated judgements sit on one row and the human ones on another, and ADR-0052 §6's whole
  point was that there is no join to write.
- **Emitting the event even for a no-op**, for a complete log of who tried. Rejected as
  ADR-0050 rejected it: a change that changed nothing must not enter the outbox.

## References

Takes the deferral ADR-0028 recorded (*"declaring a consumable URL after registration — the
repair act"*) and decides its shape; ADR-0028's own clauses stand, §5 included. Parts from
ADR-0024 deliberately, and clause 2 says why. Clauses 3 and 4 reuse ADR-0050's event rule and
ADR-0024's concurrency trick. Demanded by ADR-0052 §6.
