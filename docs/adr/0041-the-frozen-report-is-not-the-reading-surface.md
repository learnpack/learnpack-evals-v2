# ADR-0041 — The frozen report is the record, not the reading surface

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies · Evaluation

## Context

A `StudyReport` is materialized at publish and never re-emitted (12-define invariant 3). Two
consequences of that had gone unexamined, and using the console exposed both.

**The report was the only way to see a result, and it appeared only after the irreversible
act.** `GET /admin/studies/{id}/report` answers 404 until a report row exists, so evaluating a
dataset changed nothing anybody could read. The person publishing was committing to a document
they had not seen, and the act that exists to *freeze* an argument had become the act that
*reveals* it. From the outside this read as an invitation to publish in order to find out —
which is the opposite of what a signature is for.

**The report carries evidence only for failures.** `Finding` is minted one per *failing*
criterion (`judgment.py`), by design: a finding is something that went wrong. But
`criterion_outcomes` persists a quote for **every** pass — the CHECK constraint
`ck_criterion_outcomes_pass_quoted` requires it, on ADR-0021's reasoning that a pass is
somebody affirming something they saw. That passage reached no reader. The batched query that
crosses the module boundary selected five of the row's ten columns and dropped `quote`,
`locator`, `failure_mode`, `comment` and `execution_cause`.

There is a third thing neither of those is, and it has no home either. *"Which check fails most
across these twenty courses"* is the question that turns a round into an edit of the generator's
prompt, and it cannot be answered from the report: counting findings gives a numerator with no
denominator, which is precisely the arithmetic ADR-0011 retired. The denominator exists — the
instrument declares the criteria — but nothing joined the two.

The obvious fix for all three is to put more into `compose_report`. ADR-0023 §11 already
recorded why that direction is the dangerous one: `study_reports.report` is frozen jsonb, so
**anything put in it is permanent in every report published afterwards. Being wrong inwards is
unfixable; being wrong outwards is corrected whenever you like.**

## Decision

**What a person needs in order to read a study is composed on read. The frozen report is the
record of what was signed, and it is not widened to become the surface that is read.**

1. **A study's report is readable at every status**, through `GET
   /admin/studies/{id}/report/preview` — the same `compose_report` over today's inputs. The
   same function, so what a reader sees is what publishing writes. It answers at `declared`
   and `prepared` too, with the full document shape, empty sections and its gaps named, the
   way readiness informs rather than blocks.

2. **`GET .../report` keeps its 404 until a report exists**, and the preview is a separate
   resource rather than a mode of it. The bare path serves the frozen row, and the whole
   meaning of a study report is that a person committed to it; a flag that silently swapped
   which of two documents you received would be the confusion the preview exists to prevent.
   `show-preview` is likewise a CLI command of its own, not a flag on `show-report`.

3. **The preview never carries `publishedAt`, and the key is absent rather than null.** A
   preview filling it with the composition's clock would read "published" about a study nobody
   published. Absent and not null because a null renders as the epoch, and because a frontend
   type built by omission makes the field *unreadable* — the misstatement stops being a
   judgement call and becomes a compile error.

4. **The per-criterion record is its own composed-on-read resource**, `GET
   /admin/studies/{id}/criterion-outcomes`, and **not** a field inside `compose_report`. It
   carries one section per criterion **the instrument declares** — so every criterion has a
   denominator whether or not anything judged it, and a criterion nothing assessed reads `0 of
   20` rather than going missing — with each cell's own evidence: outcome, `derived`, quote,
   locator, failure mode, comment and execution cause.

5. **Nothing in it is summed across criteria.** Every distribution travels with its own
   coverage and stops there (ADR-0011 clause 3). A cross-criterion total is the single
   aggregate score that ADR retired, and a rollup is exactly where one creeps back in.

6. **A published study is read through the judgments its report recorded**, not through the
   most recent ones. Judgments are append-only; re-evaluating a course after publishing
   produces one the frozen document never saw, and reading "the latest" against a published
   study would show evidence for a document that does not reflect it. The payload names which
   of the two bases it used, and a report that recorded **no** judgment is honoured as saying
   exactly that rather than fallen back from.

7. **The human text a reader needs is joined from the instrument, not frozen into the
   report.** Claim statements, criterion statements, pass conditions and failure modes stay
   where they are authored. The published `InstrumentVersion` is immutable, so the join is
   stable; and denormalizing them would not help the reports already published, which would
   need the join anyway.

8. **`SCHEMA_VERSION` does not move.** Nothing about what publishing writes changed —
   `compose_report`'s signature, body and output are untouched, and both new resources are
   read-only, write no row and publish no event.

## Consequences

- (+) Publishing becomes signing something already read, which is what a signature is.
- (+) The passage a judge read to decide a **pass** is readable for the first time. It was
  persisted, constraint-enforced, and reachable by nobody.
- (+) "Which check fails most" is answerable with a denominator, so a round can be turned into
  an edit of the generator without counting cards by eye.
- (+) The frozen jsonb does not grow. Roughly 40 criteria × 20 courses with their quotes would
  have been added to every future report, permanently, to serve a reading.
- (+) A published study's evidence cannot drift away from the document it explains.
- (−) Two more composed-on-read endpoints to keep in step with `compose_report`. A structural
  test pins the preview against it: the two documents' key sets must differ by exactly the
  markers and `publishedAt`, so adding a key to one and not the other fails.
- (−) The preview costs what composing a report costs — around 25 round trips for 20 courses,
  because `get_contents_by_ids` pulls every content snapshot and filters in Python. It must be
  fetched on demand, never on a timer. Batching it is a registry question, deliberately not
  taken here.
- (−) `/fitness` now transfers quotes it does not read (~160 KB per call with the real
  instrument), because the widened row is one batched query rather than two near-identical
  SELECTs over one table that would drift apart.
- (−) Reports published before this carry no `documentKind`; they are frozen and are read as
  the record they are.

## Alternatives considered

- **Put the per-criterion outcomes inside `compose_report`** → rejected, and it is the one
  worth recording because it is the tempting one: it would make the report self-describing.
  ADR-0023 §11's rule decides it — the direction that cannot be undone needs a stronger reason
  than convenience, and every reading this serves is available outside the row.
- **Make `/report` answer a preview when nothing is published** → rejected: one path that
  returns either the record or a draft of it, with no way to tell from the request which you
  got. Clause 2.
- **Mint a `Finding` for passing criteria** → rejected: a `Finding` means something went wrong
  (ADR-0009, ADR-0021). Widening it to mean "an observation" would cost the vocabulary a
  distinction the whole reporting side leans on, to save one resource.
- **Denormalize claim and criterion statements into the report** (so the document is readable
  with no join) → deferred, not rejected. It has one real justification — an export consumed
  outside this console — and none of the readings here need it. Clause 7.
- **A `--preview` flag on `show-report`** → rejected with clause 2, for the reason clause 3
  exists at all: the failure mode of this whole area is a reader mistaking one document for the
  other.
- **Reading a published study's outcomes through the latest judgments** → rejected: it is the
  default that requires no code, and it is silently wrong. Clause 6.

## References

ADR-0023 §10–§11 (composed on read, and the frozen-jsonb rule this decision turns on) ·
ADR-0011 (no single aggregate score, and coverage alongside every result — clause 5) ·
ADR-0021 (a pass is affirmed and quoted; the absence-derived fail that carries none) ·
ADR-0009 (what a finding is, and grounding: a report shows what the judge read) · ADR-0037 (the
execution-error outcome and its cause, carried per cell) · ADR-0019 (ratification: why two
assessors over one study are possible at all, which clause 6 is defensive about) · 12-define
invariants 3–4 (published means an immutable report; caveats always present) ·
`backend/README.md` (the study loop, with `show-preview` in it).
