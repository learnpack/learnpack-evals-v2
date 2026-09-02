# ADR-0062 — The human side names qualities, not criteria

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Evaluation Design ·
Pedagogical Evaluation · Reporting · Calibration `[future]`

## Context

ADR-0052 §1 made the grain of the human reference instrument the quality, and said so in the
strongest available form:

> **The grain is the quality, and the id is the join.** One item per quality, and the item's
> `criterionId` **is** the `qualityId`. […] making it a primary key rather than a lookup is what
> turns the comparison from a mapping exercise into a join.

The value became a `qualityId` in that decision. **The name did not.** `criterionId` is slice-1
vocabulary, from before the automated path existed, and it has outlived the thing it named. The
code says so about itself: `orchestration/infrastructure/router.py` carries the comment
*"RubricSnapshot keeps the slice 1 name (ADR-0015); the public JSON speaks instrument"*.

So one word names two different things in one repository:

| | human — the panel's rubric | automated — the instrument |
|---|---|---|
| tables | `rubric_versions`, `criteria`, `criterion_scores` | `instrument_versions`, `instrument_criteria`, `criterion_outcomes` |
| what a "criterion" is | a Likert item about **one quality** | a verifiable condition with a written `pass_condition` (ADR-0010) |
| what its id is | a `qualityId` | a criterion's own lineage id, stable across versions (ADR-0019) |

The collision is not stylistic, and it is about to be load-bearing. The calibration ADR-0015 §4
asks for **joins the two halves**: `criterion_scores` (human) against `judgment_claims` → claims →
qualities (automated). Whoever reads that join will read `criterion_scores.criterion_id` as a
criterion, because that is what the column is called, and the join will look wrong when it is
right — or look right when it is wrong. A name that misleads at the exact point where two
subsystems meet is a defect, not a preference.

Two facts decide the timing.

**The window is open and closes by itself.** No campaign has run, so `criterion_scores` holds no
rows anywhere but on a developer's laptop, and the rename carries no data migration. This is the
same argument migration `0029` made for the reference instrument's own id — *"It is available only
now… none has run. After the first one, this id is answered data"* — and it expires the same way.

**A second, redundant column has been sitting there since ADR-0052.** Each item stores
`criterion_id` **and** `qualities`, and `qualities` is always `[criterion_id]` — true of all
twelve items of `learnpack-pedagogical-2.0.0`, by construction rather than by coincidence, since
ADR-0052 §1 made the item's id *be* the quality. Renaming the column without removing the
duplicate would leave a row saying `quality_id` and `qualities` in the same breath.

## Decision

**On the human path, an item is named by the quality it asks about. The word `criterion` is
retired from that path and stays on the automated one.**

1. **The item's id column is `quality_id`.** In storage, in the DTOs, on the wire, and in the
   seed file. What ADR-0052 decided the value would be is now what the name says.

2. **The tables are `rubric_items` and `item_scores`.** `rubric_versions` keeps its name, and
   `rubric_items` is chosen over alternatives so that `rubric_items.rubric_version_id` still reads
   as a child pointing at its parent. The lasting benefit is that the two families become legible
   at a glance: **`rubric_*` is the human reference instrument, `instrument_*` is the evidential
   argument.** Nothing on the automated path moves — not `instrument_criteria`, not
   `criterion_outcomes`, not `findings.criterion_id`, not the `criteria:` key of an instrument's
   YAML.

3. **`qualities` is dropped.** It is the same value as `quality_id`, and two sources of one truth
   is the thing this repository refuses everywhere else. Its content is reconstructible exactly —
   the `downgrade()` rebuilds it as `to_jsonb(array[quality_id])` — which is what makes dropping
   it a rename rather than a loss.

4. **The event's payload is renamed with everything else, and carries no compatibility shim.**
   `EvaluationSubmitted` writes `scores[].criterionId` into the append-only outbox, and old rows
   keep the old key forever. That would normally demand a tolerant read — the repository already
   has one, `payload.get("instrumentVersionId") or payload["rubricVersionId"]`, written for
   exactly this reason. It is not needed here, and the difference is verifiable rather than
   optimistic: `EvaluationSubmittedFact.from_payload` reads the coordinates and **never touches
   `scores`**. The key is written and never read back. A shim for a key nobody reads is ceremony,
   and it is recorded here so the next reader does not add one thinking it was forgotten.

5. **Calibration is keyed by `(Assessor, claim)`.** The GLOSSARY says
   *"keyed by **`(Assessor, Criterion)`** (not by the abstract type)"*, and that is pre-ADR-0026
   vocabulary from the same slice-1 layer as clause 1. It cannot be right: **criteria do not
   reference qualities** — the chain is `criterion → claim → quality`, and 12-define states it as
   *"the claim mediates between criterion and quality"* — so a criterion has no human number of
   its own, only one through its claim. ADR-0015 §4 already asks for the coefficient per claim.
   The grain is corrected here rather than left for the calibration ADR, because it is the same
   mistake as clause 1 wearing different clothes: **the human side names qualities, and reaches
   the automated side through claims.**

6. **Values do not change.** `"objectives-observable"` and its eleven siblings were always
   qualityIds. Nothing about what was measured, could be measured, or would be measured moves —
   which is why this is a rename and not a new version of the reference instrument. ADR-0052 §2's
   rule that a reference is stabilised by versioning it is untouched: it binds from the first
   campaign, and none has run.

## Consequences

- (+) The join that calibration needs can be read correctly by someone who has not memorised
  ADR-0052 §1. That was the whole cost being paid, and it was going to be paid at the worst
  possible place.
- (+) `rubric_*` versus `instrument_*` makes the human/automated split visible in a table listing,
  in a stack trace and in a migration — the same work module isolation does for imports.
- (+) One duplicate column and one stale vocabulary entry go away with it, both of which were
  already wrong and neither of which anyone would have opened a PR for on its own.
- (−) **It is a breaking API change**, not only a storage rename: `criterion_id` is a *request*
  field on the evaluation submit, and `criteria` is an array key in two responses. The frontend
  moves in the same PR. There is no external consumer, and nothing is deployed.
- (−) **Nothing fails at import.** There are no ORM models — `alembic/env.py` sets
  `target_metadata = None` — so every table lives in a migration plus hand-written SQL strings,
  and a missed string fails at query time, invisible to ruff and mypy. Two `**dto.__dict__`
  splats on the human path fail at request time for the same reason. The test suite is the only
  guard, which is why the rename moves module by module with its tests rather than as one sweep.
- (−) A developer's local database is migrated, not rebuilt, so `alembic upgrade head` is enough;
  but any local `events` row written before this carries `criterionId` in its `scores`, harmless
  by clause 4 and confusing to read.
- (−) The word `criterion` still means something in this repository, and now means only one
  thing. Someone reading an old note, an old commit or `docs/design/*` — which is frozen and not
  updated — will meet the old sense and have to date it.

## Alternatives considered

- **Rename the column only** (`criterion_id` → `quality_id`, tables untouched). Rejected: it
  fixes the field that misleads and leaves `criterion_scores` — the table a calibration join names
  in its `FROM` — still announcing the wrong concept. Half a rename reads as an oversight rather
  than a decision.
- **Keep `qualities` beside `quality_id`.** Rejected by clause 3: after the rename the redundancy
  stops being invisible and starts being a question every reader has to answer.
- **Rename `rubric_versions` too** (to `reference_instrument_versions`). Rejected: `Rubric` is a
  live GLOSSARY term for the human reference instrument, the parent name is what makes
  `rubric_items` legible as its child, and the diff would grow across five tables that carry
  `rubric_version_id` for no gain in clarity.
- **Do nothing and document the collision in the GLOSSARY.** Rejected: a glossary entry warning
  that a column is misnamed is a permanent tax on every reader, paid to avoid a one-time cost that
  is at its historical minimum today and rises the moment a campaign writes a row.
- **Wait until the calibration work needs it.** Rejected for the same reason, plus one: the
  calibration PR is where the join is written, and it is the worst place to also be renaming what
  the join reads.

## References

Amends the **wording** of ADR-0052 §1 and §8 (`criterionId` → `qualityId`, `criterion_scores` →
`item_scores`) and leaves their decisions intact · corrects the `Calibration` /
`CalibrationProfile` grain in `GLOSSARY.md` from `(Assessor, Criterion)` to `(Assessor, claim)`,
which ADR-0015 §4 and ADR-0026 already implied and 12-define states as *"the claim mediates
between criterion and quality"* · takes its timing argument from migration `0029` (ADR-0056) ·
ADR-0010 (what a criterion is on the automated path, and why the reference instrument is not one)
· ADR-0016 / ADR-0019 (criterion lineage, the other thing `criterionId` legitimately names) ·
ADR-0003 (the append-only outbox clause 4 reasons about) · `DATA_MODEL.md` and `GLOSSARY.md` are
updated in the same PR, per the documentation contract.
