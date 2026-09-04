# ADR-0064 — A claim is read validated where its instrument is tuned

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Calibration · Evaluation Design ·
Reporting

## Context

`RUNBOOK-calibrating.md` states the limit of everything the tuning console offers, in its own
words:

> And the limit worth stating: **self-agreement is not correctness.** A criterion can be
> perfectly stable and stably wrong, and nothing in these runs would show it. Only a human
> reading the verdicts against the content can.

Every diagnostic that console provides is internal to the machine. Traces show what was asked.
Repeats separate an unwritten threshold from a judge that cannot read. Self-agreement counts how
often the same question got the same answer. All of it measures **reliability**, and reliability
is exactly what the sentence above says is not enough.

The external evidence exists. ADR-0063 made a campaign of experts qualify a claim of an assessor
version, and the answer is a read composed on demand from data already in the store. It was put
on the study report and nowhere else, with the reason written into that ADR's alternatives:

> **Putting the badge on every surface that shows a verdict.** Rejected as scope: the study report
> is where a verdict changes a decision, and the rest can follow **if it earns its way**.

This is that surface earning it, and the argument is not symmetry. On the study report the badge
qualifies a verdict somebody is about to act on. Here it answers the question the console was
built for and cannot answer alone: **is this criterion measuring the thing the claim asserts, or
is it stably measuring something else?** A reader who does not know whether the claim tracks
expert judgment cannot tell a prompt worth fixing from a question worth rewriting, which is the
fork `notes/atribuir-un-desacuerdo-instrumento-o-assessor.md` calls the whole diagnosis.

The design behind ADR-0063 wanted both surfaces from the start — its decision 7 reads *"calibration
screen + badge in the study report"*, arguing that the screen alone would build the thermometer
without taking the temperature. What it called *the calibration screen* was a page of its own for
reading validity, which was later dropped in favour of a section inside the study report. The
second surface went with it, and the word `calibration` stayed on the tuning console for the
unrelated reason clause 10 of ADR-0063 records.

## Decision

**The reading is offered where an instrument is tuned, at the claim's grain, about the pair the
reader selected — never about the run.**

### 1. The grain is the claim, and a criterion reaches it only through its claims

The console is organised by criterion; validity is a property of `(assessor version, claim)`.
These are not the same grain and the surface may not pretend otherwise. The GLOSSARY fixes the
chain:

> **The claim, not the criterion** (ADR-0062): criteria do not reference qualities — the chain is
> `criterion → claim → quality` — so **a criterion has no human number of its own** and only
> reaches one through its claim.

So a criterion is shown the validity of **the claims it evidences**, named as such, and no
sentence anywhere says "this criterion's validity". Where a criterion evidences several claims it
shows several readings rather than an aggregate: ADR-0063 §1 already refused attribution across
claims, and averaging them here would smuggle it back.

### 2. The link comes from the instrument, never from the judgment

`criterion.claim_ids` is read off the instrument version. A judgment carries only the claims that
survived coverage — one whose criteria were all `not_applicable` is excluded and has no row at all
— so deriving the link from a run would silently drop exactly the claims a reader is least likely
to notice missing. `criterion_outcomes.py` already carries this warning at its own call site.

### 3. The campaign stays explicit and optional on this surface too

ADR-0063 §7 is unchanged and applies verbatim: the reader names the campaign, nothing is
inferred, no campaign means **no badge** rather than `unvalidated`, and two campaigns are never
averaged. A console is not a reason to default a coordinate — the objection was that one URL
would mean different things over time, and this page is reached by URL from the study report.

### 4. What is qualified is the selected pair, and a dry run changes nothing about it

The claim status a dry run produces and the validity of that claim sit next to each other, and
confusing them would be easy and wrong. Validity is a property of the published pair measured
against a panel; a dry run persists nothing, is allowed on drafts, and could not move it. The
screen says so where the two appear together.

### 5. Executable and measurable are different states, and both are said out loud

A dry run needs neither ratification nor an identity row: that is the point of the console
(`preview_evaluation.py`). A validity read needs the assessor's id, which exists only from the
first ratification onward (ADR-0019 §2). So a package can be perfectly runnable here and have
nothing to read, and a version can resolve while never having judged anything.

Each of those is reported as itself — no identity yet · not ratified against this version, so it
cannot have judged with it · judged nothing of this campaign's courses — rather than as one empty
table. This is ADR-0011 §3 applied to a screen: *nobody measured this* and *we measured it and it
does not conclude* stay apart.

### 6. Tuning a draft version reads empty, and that is the honest answer

A draft has judged nothing, so its claims come back unmeasured. The reading is least available
exactly when a reader is most in the middle of the work, and the screen states the reason instead
of implying the claims failed. Carrying a claim's calibration across a version bump is what would
fix it, and it is deferred to clause 8.

### 7. It remains a read

No endpoint is added, no table, no event, nothing persisted (ADR-0063 §8). Both coordinates the
console lacked were already on the wire: the assessor's id travels with the package, and the
criterion-to-claim link travels with the instrument. The inbound deep link carries the campaign so
that arriving from a weak claim does not ask the reader to choose it twice.

### 8. `[future]` — a claim's calibration across an instrument version bump

The design already names the rule: a claim keeps its calibration when its id, its statement and
its quality are unchanged, and is born `unvalidated` otherwise, with ADR-0019 §3 computing the
diff. Building it means deciding what a reading *measured on another version* may claim about
this one, and that is a decision with alternatives, not a convenience. Until it exists, clause 6
holds.

## Consequences

- (+) The one piece of external evidence about an instrument becomes reachable from the page
  whose own runbook says internal evidence cannot supply it.
- (+) Nothing new is computed, stored or served. The feature is two coordinates meeting data that
  was already being fetched by this page for other reasons.
- (+) The nav already groups this console under *Human evaluation*, which was arguably wrong while
  the page held nothing human. It stops being wrong.
- (−) A fourth coordinate on a page that already asks for three, and the only one that is not part
  of the run. It is placed outside the numbered steps for that reason, and it can be ignored.
- (−) While tuning a draft the reading is empty precisely when it would help most (clause 6). The
  honest empty state is a worse product than the answer clause 8 defers, and knowingly so.
- (−) A second surface now consumes the validity read, so a change to its shape is a change to two
  screens. The badge moves out of the study report's folder to stop that from being a surprise.

## Alternatives considered

- **Attaching validity to the criterion rows of the outcomes table.** Rejected by clause 1: a
  criterion has no human number, and putting one beside it would invent the attribution ADR-0063
  §1 refuses.
- **Showing it only after a dry run**, beside the claims the run produced. Rejected: the question
  is *should I touch this criterion at all*, which precedes the run. The run-side badge is kept as
  a contrast, not as the entry point.
- **Defaulting to the most recent campaign** so the console needs no new control. Rejected by
  clause 3, which is ADR-0063 §7 unchanged.
- **Rolling a criterion's claims up into one badge.** Rejected: two claims of one criterion
  disagreeing is a finding about the instrument, and an average is the one presentation that
  destroys it.
- **Leaving it on the study report and linking harder.** Rejected: the reader who is editing YAML
  is not going to leave the console to check whether the claim was ever validated, and a check
  nobody performs is a check that does not exist.

## References

Extends ADR-0063 (which computed this reading and scoped it to one surface, and whose clauses 7,
8 and 9 apply here unchanged) · ADR-0062 and the GLOSSARY for why the grain is the claim and a
criterion has no human number · ADR-0019 §2 for the identity row minted by the first ratification,
and §3 for the version diff clause 8 would need · ADR-0011 §3 for why each unavailable state is
named rather than collapsed into one blank · ADR-0016 for the assessor package's identity ·
`RUNBOOK-calibrating.md` for the limit this closes · the design and its ten decisions in `notes/`
(working, not maintained).
