# ADR-0036 — Ratification is offered at both gates, and the delta is decided criterion by criterion

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation · Identity

## Context

ADR-0019 made ratification the act that lets an assessor evaluate against a concrete
instrument version, and clause 5 made it a forcing function: no criterion reaches a
**persisted** judgment without a conscious decision by the assessor's author. Block 6
realized it as one CLI command, `ratify-assessor`, and the evaluation router states the
stance in prose: "the deliberate acts (profile, accept, ratify, evaluate for real) stay in
the CLI".

That stance is now the thing standing between a calibrated assessor and a study.
`drafts-hybrid:2` has been exercised against the real model and its answers are on the
calibration page; not one of its semantic criteria has produced a persisted judgment,
because the act that would allow it needs a terminal, the exact instrument version id, an
admin email and knowledge of a flag nobody has had to use yet. The team reads the dry runs
in the console and then cannot act on what it read there.

The console's second gap is the one that makes the first hard to even notice: **there is no
place that answers "who can judge, and against which version"**. The state is split across
three stores — the in-code registry of packages (`AUTOMATED_ASSESSORS`, published as
`GET /admin/assessor-packages`), the `assessors` rows, which for an automated assessor exist
only once it has been ratified at least once, and `assessor_ratifications`. The one endpoint
that lists assessors returns humans and automated mixed together and does not say which is
which; the ratification relation is readable only per instrument version, inside a study's
readiness.

Two facts constrain the fix.

1. **The stance being amended is a docstring, not a decision.** The counter-example is
   already in the codebase: publishing an instrument version is a human act, is irreversible,
   and is exposed as `POST /admin/instruments/{id}/publish` behind a confirmation dialog
   (design 12, invariants 4 and 5). Nothing distinguishes ratification from it on the axis of
   deliberateness.
2. **The act is not a yes/no.** Against a later version of the lineage, ADR-0019 §3 demands
   an explicit decision per new or changed **executed** criterion — the CLI's
   `--confirm <criterion_id>`. A console button that submitted the act with one click would
   keep the surface and lose the forcing function, which is the only reason the act exists.

## Decision

**Ratification is offered at both gates — the CLI and the admin console — behind one use
case; and the delta that ADR-0019 §3 demands is decided criterion by criterion at whichever
gate is used.**

1. **One act, two gates.** `RatifyAssessor` is an application use case; `ratify-assessor`
   and `POST /admin/assessor-packages/{name}/{version}/ratify` are two callers of it. Neither
   gate holds a rule the other lacks, so they cannot drift — the same argument that keeps
   `evaluate --dry-run` and the calibration page on one `PreviewEvaluation`.

2. **The forcing function is preserved literally, not in spirit.** The diff over the last
   ratified version of the lineage is computed mechanically; every new or changed executed
   criterion is refused until it is confirmed **by its own id**. The console shows each such
   criterion's `pass_condition` beside its own checkbox: what is being confirmed is that the
   executor still realizes *that* text. A single blanket confirmation is not offered at
   either gate.

3. **The act spans two modules, and the composition root wires both.** Minting the automated
   assessor's row is Identity's — it is Identity's aggregate, and the refusal when a stored
   `source_config` differs from the code is Identity's invariant (ADR-0016 clause 2: the
   artifact changed without a version bump). Recording the ratification is Evaluation's.
   Neither module commands the other: the CLI function and the HTTP handler each call the two
   use cases in one transaction, exactly as the CLI already did inline. Identity's public
   surface stays read-only (05-connect rule 2, intact).

4. **Every refusal is named at the boundary, not merely described.** The delta answers
   **409** with an object detail — `{message, criteria: [{criterion_id, change,
   pass_condition}]}` — because the ids to confirm are contract, not prose (the shape ADR-0031
   established for the near-miss 409). A draft target, a foreign lineage, coverage that does
   not decide every criterion of the version, and a drifted `source_config` each answer 422
   with their own cause.

5. **The console states what the act commits to before it is taken.** Not "are you sure":
   that this is what lets the assessor's judgments **persist**; that it records who and when;
   that it does not change the assessor's identity and does not transfer to a later assessor
   version; and that there is no way to undo it. The calibration the decision rests on is the
   team's reading of the dry runs — the act verifies coverage, never quality.

6. **The other three deliberate acts stay where they are, for reasons of their own.**
   `profile-content` and `reprofile` pick a fetcher and a base directory, which is an
   operational choice, and the profiling module's stance already kept them off the calibration
   page. `accept-extraction` is a judgement about an adapter version's code, not about a row
   the console displays. `evaluate` for real is work rather than a decision — minutes of LLM
   calls that a request cannot report at the end — so exposing it means the started-not-awaited
   machinery the preview runs already needed; deferred, not refused. This ADR moves one act,
   named.

7. **Un-ratifying stays unbuilt.** A ratification is the record of a decision that was made;
   deleting it would not unmake the judgments persisted under it, and the report that cites
   them is immutable. If the decision turns out to have been wrong, the exits that exist are
   the honest ones: a new assessor version, or a new instrument version that nothing has
   ratified yet.

## Consequences

- (+) The loop closes in one place: read the dry runs on `/admin/calibration`, see what each
  package covers and what it has ratified on `/admin/assessors`, ratify, evaluate. Today the
  middle step leaves the console.
- (+) The three-way split of assessor state (registry, rows, ratifications) becomes one read.
  A package that has never been ratified is visible **as such** — under the old surface it did
  not appear at all, since its row is created by the first ratification.
- (+) The rules leave `cli.py` for an application use case with its own tests, where they can
  be exercised without a subprocess or captured stderr.
- (−) A second gate on an act whose whole purpose is deliberation. Clause 2 is the mitigation
  and it is a real one: the console asks for *more* than the CLI does, since it shows the text
  being confirmed rather than accepting an id typed from an error message.
- (−) The refusal vocabulary is now duplicated in two dialects — exit codes plus stderr at one
  gate, status codes plus detail objects at the other. The existing CLI tests pin the strings,
  so a translation drifting is a failing test, not a silent change.
- (−) Ratifying is one click away from an admin who has not read anything. That is true of
  publishing an instrument too, which is the more consequential act, and the answer is the
  same: the dialog says what is being committed to and nothing is defaulted.

## Alternatives considered

- **Keep the act CLI-only and have the page render the command to copy** → rejected: it
  concedes that the console must show the state (the harder half of the work) and then refuses
  the one line that acts on it. A copied command is also the shape most likely to be run with
  the wrong version id, since the id is retyped rather than selected.
- **One blanket confirmation for the whole delta** → rejected by ADR-0019 §3. It converts a
  per-criterion decision into a per-version one, which is precisely the "silent drift"
  alternative that ADR already refused.
- **Put the endpoint in Identity's router, since it mints the assessor** → rejected: the
  ratification table, the instrument gateway and every rule about coverage are Evaluation's;
  Identity would end up holding a use case whose invariants it cannot see.
- **Add a write to Identity's published language so Evaluation can call it** → rejected: a
  cross-module command, which 05-connect rule 2 forbids and which nothing here needs — a
  composition root wiring two use cases in one transaction is the shape the CLI already used.
- **Ratify automatically when coverage decides every criterion of a newly published version**
  → rejected, and it is the tempting one, since the mechanical check would pass. It is
  ADR-0019's own rejected alternative ("automatic compatibility without ratification"): a new
  criterion would reach a persisted judgment with no one deciding it had been realized.
- **Expose all four deliberate acts at once** → rejected as scope: three of them have reasons
  of their own (clause 6), and `evaluate` in particular needs the async-run machinery rather
  than a route.

## References

ADR-0019 (the act, its per-version scope, and the §3 delta this ADR carries to a second gate;
§5's forcing function is what clause 2 preserves) · ADR-0016 clause 2 (identity of the
artifact — the `source_config` drift refusal that stays Identity's) · ADR-0018 (coverage must
decide every criterion of the version) · ADR-0031 (an error detail that carries data is an
object) · ADR-0034 (`drafts-hybrid:2`, the calibrated assessor with nothing persisted — the
case that exposed the cost) · design 12 invariants 4–5 and
`POST /admin/instruments/{id}/publish` (the precedent: a human act with an HTTP surface) ·
05-connect rule 2 (cross-module reads yes, writes no) · `backend/app/modules/evaluation/
infrastructure/router.py` (the docstring stance this ADR amends).
