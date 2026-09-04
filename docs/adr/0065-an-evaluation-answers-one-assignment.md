# ADR-0065 — An evaluation answers one assignment

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Evaluation · Evaluation Orchestration ·
Reporting

## Context

A campaign's report can change because of something that happened in a later round. The same
expert evaluates the same course in two campaigns pinning the same reference instrument version;
the two answers collapse to the latest, and that latest becomes what **both** campaigns count. The
older campaign stops saying what it found when it ran.

That contradicts ADR-0060's own thesis — *a campaign's result is read inside the campaign that
produced it* — and nothing frozen protects it, because that report is composed on read (ADR-0060
§7).

The immediate cause is that `collapse_latest_per_assessor` keys on
`(assessor, content, instrument version)` with no campaign in it. The cause underneath is a
premise: an evaluation is campaign-agnostic, and one submission may satisfy several campaigns.

### The premise was never argued

It is asserted three times and reasoned once, in a circle.

- **ADR-0002's context** is about incremental provisioning and rotation: starting with the experts
  you have, adding more, cancelling and reassigning when somebody does not deliver. Multi-campaign
  satisfaction appears nowhere in its decision, its consequences or its alternatives. It appears
  once, in an implementation note, phrased as an effect: *"This way the same evaluation can satisfy
  several campaigns that requested it."*
- **ADR-0005's context** is about two other problems: repetitions of one automated source run N
  times to measure dispersion, and content versions. Its own diagnosis is that anti-duplication had
  been made part of the aggregate's identity. Dropping that uniqueness is what lets an `LLMJudge`
  run N times. **It does not require campaign-agnosticism**; the two travelled together.
- ADR-0005's alternatives reject a `campaign_id` for two reasons. *"Breaks multi-campaign"* assumes
  the value of the thing in question. *"And the correct identity"* does not hold: the same ADR fixes
  identity as the surrogate `evaluationId`, and an attribute does not touch it.
- **ADR-0060 §1** then permits the sharing *because ADR-0005 made it legal on purpose*.

### The one good argument, and where it stops

Nobody wrote it down, and it is real: do not make an expert answer the identical form about the
identical course twice. SME time is the scarcest resource here, and a second answer with no washout
is contaminated by memory of the first, so it is not independent data either.

That argument covers **concurrent** campaigns whose scopes overlap. It is exactly wrong for a
**follow-up** campaign, where a fresh answer is the entire point and reusing the old one would hide
the drift the round exists to detect.

And the defect lives only in the follow-up case. When both assignments exist before the answer, the
API produces one evaluation and refuses the second submission with a 409; sharing works and nothing
moves. When the second campaign assigns *after* the first answer, a second evaluation appears and
rewrites the first campaign's numbers. **The premise shares where sharing is right and fails where
sharing is wrong.**

There is a second face. Today, when two campaigns both assign the same expert to the same course,
answering one marks the other's assignment `submitted`. That campaign's progress screen says the
expert delivered. They delivered to the other round.

### Why now

No campaign has run and nothing is deployed, so `evaluations` holds no answered data anywhere but on
a developer's machine. This is migration 0034's argument, and it expires the same way: after the
first real campaign, changing what an answer belongs to is rewriting the record.

## Decision

**An evaluation answers one assignment, and therefore belongs to one campaign.**

This **amends** — it does not supersede — ADR-0002's implementation note, ADR-0005's rejected
alternative and ADR-0060 §1. The decisions of all three stand.

### 1. A human evaluation records the assignment it answers

Null for an automated one, which answers no assignment. The id already arrives on the wire and is
already used for three guards; it stops being discarded.

The Evaluation module still knows nothing of campaigns. It knows which assignment it answers, and
the campaign is reached through that — which is the line ADR-0002 drew when it said the link to the
campaign is the assignment. The link is now recorded rather than reconstructed.

### 2. Membership becomes one rule

An evaluation belongs to the campaign of the assignment it answers. The set lookup on
`(content, assessor)`, the instrument-version check and the special case that keeps automated
evaluations out of campaign reports all dissolve into that single clause. ADR-0060's thesis is
unchanged; it is realized more exactly, and its rule is still the completion policy's rule, so the
second definition it warned about still never exists.

### 3. One submission advances one assignment

The completion policy stops marking every matching open assignment and marks the one that was
answered. Quorum still counts submitted assignments per campaign (ADR-0002 §3), and a campaign stops
reporting that it received something delivered to another round.

### 4. Sharing across campaigns ends

Two campaigns that both want an expert's reading of one course now get one each. That is the cost,
stated: the concurrent-overlap case pays an extra form. The follow-up case, which is the one the
design anticipates, gets what it actually wanted.

### 5. Repetitions still coexist

ADR-0005 clause 1 is untouched. Identity remains the surrogate id, there is still no uniqueness on
`(assessor, content, instrument version)`, and an automated assessor run N times for dispersion is
unaffected because it answers no assignment. What changes is the human path only.

### 6. An evaluation with no assignment belongs to no campaign

This generalizes what ADR-0060 §1 already said about automated evaluations. It stops being a written
exception and becomes a consequence of clause 2.

### 7. A correction, in a campaign, is unreachable — and its counter goes

Within one campaign an assessor answers a course at most once: the partial unique index allows one
active assignment per `(campaign, content, assessor)`, re-submitting one already submitted is a 409,
and a submitted assignment cannot be cancelled. So the collapse never fires inside a campaign, and
`superseded_count` — labelled *Corrections* on the screen — **can only ever have counted the defect**.
Both go. A counter that cannot move is not a zero, it is a claim the system cannot support.

### 8. Nothing is backfilled

Rows written before this carry no assignment and therefore belong to no campaign, which is exactly
what they are. Inventing an attribution nobody recorded would be worse than admitting there is none,
and there is no answered data to lose.

### 9. `[future]` — a correction, and intra-rater consistency

There is no way today for an expert to revise an answer; the 409 is the whole story. Whether that
should exist, and what a revision means to a report already read, is its own decision. The same data
makes test–retest consistency deliberate rather than accidental, and that is a new reading, not a new
collection.

## Consequences

- (+) The defect stops being something to mitigate and becomes unrepresentable. There is no rule
  choosing between two answers, because a campaign never has two.
- (+) `campaign_scope` loses the `submitted`/`counted` pair, the campaign report loses a counter and
  a per-row flag, and ADR-0060 §1's three-part rule becomes one clause. The fix is a net deletion.
- (+) A campaign's progress stops crediting it with a delivery it never received.
- (−) Two concurrent campaigns overlapping on `(course, expert, instrument version)` now cost two
  answers. Nobody has met that case, and the second answer would have been the contaminated one.
- (−) ADR-0002's implementation note and ADR-0005's alternative are now partly historical. They are
  not edited; this ADR is where a reader finds out.
- (−) Old rows in `events` carry no `assignmentId`, so replaying one attributes nothing. Acceptable
  only because nothing is deployed, and stated so that it is not mistaken for a general guarantee.

## Alternatives considered

- **Keep the premise and make the collapse campaign-aware** — prefer the campaign's own answer, fall
  back to a shared one. Rejected: it mitigates rather than closes, and it buys a permanent
  distinction between an own answer and a shared one, with a fallback rule and a new label for
  answers from another round, all to preserve a case nobody has met.
- **`campaign_id` on the evaluation.** Rejected for the reason ADR-0002 and ADR-0005 gave and this
  ADR keeps: the link belongs on the assignment, which is what reassignment moves. A campaign id
  would partition without passing through the act that produced the answer.
- **Recording the link the other way, on the assignment.** Rejected: the policy that would write it
  runs after the evaluation commits, leaving a window in which an answer exists attributed to
  nothing. Written with the evaluation, in its own transaction, there is no such window.
- **Freezing the campaign report** so a later round cannot move it. Rejected by ADR-0060 §7, and it
  would preserve the wrong number rather than stop producing it.

## References

Amends ADR-0002's implementation note (one submission advancing every matching assignment) and its
`Evaluation` campaign-agnosticism · amends ADR-0005's rejected alternative, while leaving its
clauses 1–3 intact · amends ADR-0060 §1's membership rule, whose thesis it realizes · ADR-0006 §3
for the collapse rule this makes unreachable inside a campaign, and which stays for the automated
sampling it was also written for · ADR-0056 §5 for the different-pinned-version case, which was
always separated cleanly and is unaffected · ADR-0003 for the replay this keeps idempotent ·
migration 0034 for the argument that this window is open only until the first campaign runs.
