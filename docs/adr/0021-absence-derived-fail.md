# ADR-0021 — The `fail` derived from absence: outcome without a quote, with recorded origin

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation

## Context

Three rules in force collide in a case the first instrument makes inevitable:

1. **ADR-0009**: without a quote it is not evidence — every verdict points to verbatim text.
2. **ADR-0010 / 12-define**: each criterion declares `on_missing_evidence` — the consequence
   of the required data being absent from the content. With `fail`, **the absence itself is
   the defect** (ADR-0009 §4: absence is a first-class finding). Six of the eleven
   criteria of `learnpack-course-qa-v1` declare it that way; their most important case is
   exactly that ("No objectives declared at all — the generator omitted them").
3. **ADR-0018 §5 / 13-code §3.5**: the `criterion_outcomes` CHECK requires a quote on every
   `pass`/`fail` ("scored requires a quote").

An `absent` profile entry **has no quote by construction** (text that does not exist
cannot be quoted; the `profile_entries` CHECK guarantees it). The `fail` the mechanical
derivation produces from it is, then, a `fail` without a quote — and rule 3 makes it
**impossible to persist**. The letter of ADR-0018 §5, written with executor-produced
outcomes in mind, blocks the outcome that ADR-0009 §4 and ADR-0010 require.

## Decision

**The outcome's origin is recorded in the row (`derived`), and the quote requirement is
conditioned on that origin.**

1. `criterion_outcomes` gains **`derived boolean not null default false`**: `true` = the
   outcome was produced by the mechanical derivation (absence with `on_missing_evidence='fail'`);
   `false` = it was produced by an executor (human or automated) looking at the evidence.
2. The CHECKs become: **`pass` ⇒ quote and not derived** (a pass is always someone
   affirming something they saw — the mechanics never derives pass) · **`fail` ⇒ quote OR derived** ·
   the three non-scored states still require no quote.
3. **The derived fail produces a finding** — the absence is the actionable finding — with
   `quote` null and a mechanical `failure_mode` `"required data absent: <data_requirement_ids>"`,
   never one chosen from the declared ones (choosing one would be pretending an executor
   judged). Its evidence is the profile's `absent` entry: the citable record that the
   adapter looked and there was nothing, verifiable against the package.
4. The other mechanical deriveds (`not_applicable`, `no_evidence`, `not_assessed`) also
   carry `derived=true` — the origin is uniform and queryable (useful for `evidence_basis`
   and the reports' caveats).

## Relationship with ADR-0018 and ADR-0009

**Refines ADR-0018 §5** (it does not supersede it): exact coverage over five states and
everything else stays the same; "scored requires a quote" becomes "**executed** scored
requires a quote". **Realizes ADR-0009 §4**: absence is a first-class finding also in
persistence. The ADR-0009 guarantee remains intact where it matters: everything an
executor affirms still requires a verbatim quote.

## Consequences

- (+) The central case of six real criteria (a generator omitting what it should declare) is
  persistable and produces its actionable finding.
- (+) `derived` distinguishes in data "someone judged it" from "the mechanics derived it" — the
  human layer 2 (ADR-0015) can filter what to review.
- (−) A finding without a quote is an exception to the general form; reports must show it
  with its cause ("absent data") so it is not read as an incomplete finding.
- (−) The GLOSSARY adjusts the phrase "outcome + quote" wherever it implies an unconditional
  quote.

## Alternatives considered

- **Derived fail without a finding** → rejected: the claim is refuted but the actionable
  list loses the most useful signal exactly in the case "the absence IS the finding".
- **Quoting the `absent` entry as a synthetic quote** ("<absent: learning_objectives>") →
  rejected: a fabricated quote satisfies the CHECK by lying — the void disguised as text.
- **Mapping absence+`fail` to `no_evidence`** → rejected: it nullifies `on_missing_evidence='fail'`
  (ADR-0010) and hides the defect the criterion exists to catch.

## References

ADR-0009 (§4: absence is a finding) · ADR-0010 (`on_missing_evidence`) · ADR-0018 §5
(the refined rule) · 13-code §3.5 (the CHECK this ADR corrects) · 12-define §Content
Profiling inv. 3 (the explicit `absent` entry — the evidence of the derived fail) ·
`learnpack-course-qa-v1` (the six criteria with `on_missing_evidence: fail`).
