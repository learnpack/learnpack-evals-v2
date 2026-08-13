# ADR-0038 — The upstreams that may serve a model are assessor identity: the provider deny-list

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Identity

## Context

ADR-0034 drew the identity/transport line with a testable rule: *"a transport change may
alter whether and when an answer arrives, never which answer arrives"* — and its §3 left
one question deliberately open (pinning the upstream that serves a routed model), noting
that the trace records which provider answered, so the size of the problem could be
measured from real runs before deciding.

The calibration campaign measured it. Behind one model id, one upstream served **every
capped runaway of the campaign — seven of seven** — including cuts where its
undisableable reasoning consumed the judging budget and truncated the answer; the clean
retry (ADR-0037 §7) lost for the first time to a four-draw streak of that same upstream,
costing an `execution_error`. A second upstream billed invisible reasoning at 11–100×
the visible answer under **both** disable flags (`effort: "none"`, `enabled: false`),
and once returned a null-content 200 carrying only its reasoning — the campaign's first
`execution_error`. Meanwhile the same questions, byte-identical, answered cleanly under
every other upstream. The router draws an upstream per request, so two evaluations under
one assessor identity can be served by materially different judges: at the provider
grain, the rule that keeps transport free of identity — *never which answer* — is
empirically false.

## Decision

**An LLM-carrying assessor declares which upstreams may NOT serve its calls; the list is
part of its identity.**

1. **`DENIED_PROVIDERS` is pinned in the assessor's package and declared in
   `SOURCE_CONFIG`.** Changing the list — adding an offender, forgiving one — is a new
   assessor version (ADR-0016): it changes the pool of judges an evaluation can draw,
   which is exactly what calibration is conditioned on.
2. **It travels per request through the existing extra-wire-fields seam** (the router's
   `provider: {"ignore": [<slugs>]}` request field). The platform client is untouched:
   the deny-list is semantics riding the channel ADR-0034 §1 already declared for
   semantic wire fields, and transport keeps re-versioning nothing.
3. **Deny, not allow.** An allow-list buys consistency at the availability price
   ADR-0034 §3 already judged worse than the variance; a deny-list excises measured
   offenders and keeps the router's mobility for everyone else. The §3 future shape — a
   quantization floor plus an acceptable-provider list — remains open and untaken.
4. **The bar for an entry is repeated, trace-documented failure, never a single
   incident.** Each entry cites its evidence where it is pinned. The initial list:
   `sail-research` (every capped runaway of the campaign; reasoning past both disable
   flags into the judging budget) and `atlas-cloud` (reasoning billed at 11–100× the
   visible answer under both flags; one null-content 200). One incident — e.g. the
   3,491-token bill served once by another upstream — is watched, not listed.
5. **Relationship to ADR-0034: amends §1's identity enumeration** (the semantic surface
   gains "which upstreams may not serve the calls") and answers part of §3's open
   question with the evidence it asked for. Nothing is superseded: the transport rule
   stands for everything that is actually transport, and the fingerprint/ratification
   guard governs this list like any other `SOURCE_CONFIG` constant.

## Consequences

- (+) One assessor identity draws from one declared pool of possible judges; the
  provider-conditioned failures the traces documented stop entering calibration data.
- (+) The act of changing the pool is visible, versioned and refused at ratification
  when it drifts — instead of an account setting nobody's identity system can see.
- (−) List maintenance is version bumps, deliberately: forgiving an upstream is as much
  an identity change as denying one.
- (−) A deny-list is reactive by construction — a new bad upstream must first be caught
  by the traces. Accepted: the budget and retry machinery (ADR-0037) bound what a new
  offender can cost while the evidence accumulates.
- (−) The slugs couple to the router's vocabulary (an ACL concern, like the model ids
  ADR-0034 already pins with the provider namespace inside them).

## Alternatives considered

- **The list from an env var** → rejected: the model-id-from-env mistake one door over
  (ADR-0034 §2) — two runs under different lists would be two judges wearing one
  identity, invisibly.
- **An allow-list** → rejected for now: consistency at an availability risk judged worse
  than the variance (ADR-0034 §3's recorded reasoning); reconsidered only as part of the
  full pinning decision.
- **Account-level provider settings on the router's dashboard** → rejected: outside the
  repo, silently mutable, invisible to `SOURCE_CONFIG` and the ratification guard — the
  identity system cannot see it change.
- **A platform-client constant** → rejected: shared transport re-versions nobody while
  changing every assessor's judge pool at once — the identity blur and spurious
  invalidation ADR-0034 §3–5 exist to prevent.

## References

ADR-0034 §1 (the identity enumeration this amends; the extra-wire-fields seam the list
rides) · §2 (the env-var rejection this reuses) · §3 (the open pinning question and its
"measure first" instruction — the traces this decision cites are that measurement) ·
ADR-0016 (change ⇒ version ⇒ identity) · ADR-0037 (the failure budget and clean retry
that bounded these offenders while the evidence accumulated; the `execution_error` rows
that recorded them) · `backend/README.md` §*What repeated runs tell you* · the router's
provider-routing request schema (`provider.ignore`, slugs).
