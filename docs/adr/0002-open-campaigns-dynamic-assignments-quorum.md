# ADR-0002 — Open campaigns, dynamic assignments and quorum by submissions

**Status:** accepted · **Date:** 2026-07 · **DDD context:** Evaluation Orchestration

## Context
The operational reality is not "having all the SMEs and all the assignments before starting":
- You start with the available experts and **add more over time**.
- An expert may **not deliver**, or deliver only part of what was assigned → you need to **cancel**
  or **reassign**.

The previous model conflated *provisioning* (assignments) with *goal* (quorum): it fixed "N distinct
assessors per content when creating the campaign" and defined completeness as "all assignments
submitted". That does not support incremental provisioning or assignment rotation.

## Decision
1. **`EvaluationCampaign` = open aggregate (config + scope), not the transactional owner of the
   assignments.** It fixes `rubricVersion`, `requiredEvaluationsPerContent` (threshold) and `metadataView`.
   Lifecycle `Draft → Open → Closed`. **Opening does not require all the assignments.**
2. **`Assignment` = its own aggregate, small, with lifecycle** `Assigned → Opened → Submitted` |
   `Cancelled`. Reassign = cancel + new assignment to another assessor. Invariant: ≤1 active assignment
   per `(campaign, content, assessor)`; only cancellable if not `Submitted`.
3. **Quorum = completeness threshold over submissions, not provisioning.** A content item is
   `Completed` when the number of **distinct assessors who submitted** a valid evaluation reaches
   the threshold. Cancelled/incomplete assignments **do not count**.
4. **Eventual completeness via policy:** `EvaluationSubmitted` → count distinct assessors →
   `≥ threshold` → `ContentEvaluationCompleted`. It is not a transactional invariant of a large aggregate.

**Implementation note (aligned with 08 §5 and ADR-0005):** the `Evaluation` is **campaign-agnostic**
(no `campaign_id`). The link to the campaign is the `Assignment`: on submit, all open assignments of
`(assessor, content)` whose `campaign.rubricVersion` matches are marked `submitted`, and
the completeness of `(campaign, content)` = `COUNT(assignments submitted) ≥ required`. This way the same
evaluation can satisfy several campaigns that requested it. Human anti-duplication (one
submission per assignment) lives in the `Assignment`, not in an `Evaluation` uniqueness — see
ADR-0005.

## Consequences
- (+) You can **start now** with few experts and add more without restructuring anything.
- (+) Cancelling/reassigning is natural; only deliveries move the needle.
- (+) Small `Assignment` → no contention; scales well.
- (+) Human anti-duplication lives in the `Assignment` (one submission per assignment, ADR-0005),
  so counting `assignments submitted` is safe without relying on an `Evaluation` uniqueness.
- (−) Completeness is eventual, not immediate (acceptable: it is an asynchronous human process).

## Open questions (do not block the MVP)
- Submission without a prior assignment? (MVP: no — the assignment feeds the pending list.)
- Over-quorum? (allowed; completes upon reaching N; extras are stored.)
- Changing N while the campaign is open? (MVP: fixed.)

## Alternatives considered
- **Fixed provisioning (N assignments at creation) + completeness = all submitted** → rejected:
  it does not support incrementality or rotation; fragile in the face of non-delivery.
- **Campaign owns all the assignments (large aggregate)** → rejected: contention and a giant
  aggregate; violates "small aggregates".
