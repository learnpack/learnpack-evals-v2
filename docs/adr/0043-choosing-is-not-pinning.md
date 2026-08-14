# ADR-0043 — Choosing is not pinning, and publishing is signing off

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies

## Context

The console renders a study's setup as four numbered steps — *Pin the instrument · Pin the
assessor · Compose the dataset · Open the study* — and names three of them after the verb the
aggregate uses internally. The domain never asked for that sequence. `Study._maybe_prepare`
derives `prepared` from "both pins plus a composed dataset, **in any order**", and
`ComposeDataset` publishes no event at all precisely because "the recipe evolves freely until
`open` fixes it" (`domain/events.py`). The order, the numbering and the word *pin* are the
console's inventions, and each of them costs something.

**The asymmetry has no defence.** The dataset is replaceable until the study opens;
`pin_instrument` raises `InstrumentAlreadyPinned` *regardless of status* — including on a
study still being set up — and no endpoint exists to correct it. The three are consumed at
the same moment: `batch_runs.prepare` refuses any evaluation unless the study is `open`. So a
mistyped dropdown on a draft does not cost a correction; it costs the study. That is not the
reproducibility ADR-0042 bought. It is ceremony that arrived attached to it.

**Opening produces nothing a person can observe.** It fixes the dataset and lets the batch
run, and the only thing anyone does next is run the batch. As its own button it asks the
reader to perform a step whose entire effect is to enable the following step.

**`purpose` holds two concepts.** The GLOSSARY defines an `EvaluationStudy` as "an evaluation
round with a purpose (initial / regression / comparison)" — a **typology**. The column holds
free text, and every surface renders it as the study's title. The word was borrowed for a job
it does not name, and the concept it does name has nowhere to live.

**"Publish" names an act that publishes nothing.** Nothing becomes visible to anyone who
could not already see it: ADR-0041 established that a study's result is readable before it is
frozen, and built the preview that proves it. There is no external audience, no feed, no
second reader. What the act actually adds is already in the schema under its right name —
`published_by`. It is a **signature**: a person taking responsibility for a document, and
closing it.

## Decision

**A draft chooses; opening pins. Opening is not an act of its own. A study is named and
described. And the act that closes a study is a signature.**

### 1. The draft chooses; opening pins

1. **`select_instrument` and `select_assessor` replace freely while the study is mutable** —
   the same guard `compose_dataset` already uses, and the same reason: nothing has consumed
   them yet. From `open` onwards they are immutable, which is where they were always headed.

2. **Selecting publishes no event**, exactly as composing the dataset does not. `StudyOpened`
   already carries the whole triple — instrument version, assessor, briefs and contents — so
   the log loses no fact. `InstrumentPinned` and `AssessorPinned` are therefore removed. Rows
   already written stay and are read as the record they are.

3. **This amends ADR-0042 §8 and nothing else.** Clause 9 (every read of a study filters
   judgments by its pinned assessor), clause 10 (the batch takes the assessor from the study,
   and refuses a disagreeing one) and clause 11 (an unpinned study is not repairable after
   opening) are untouched, because all three speak about a study that has opened. What §8
   claimed — that the pin must precede opening — is preserved in the only form that ever did
   any work: **when the first judgment can exist, the triple is already fixed and cannot
   change**. Moving the commitment from "the moment somebody chose" to "the moment anything
   could depend on the choice" narrows nothing, because nothing can depend on it earlier.

4. **`declared` and `prepared` stay in the model and leave the screen.** `prepared` is what
   tells the console whether the study can be started; it was never a state a reader needed
   named. Both render as *Draft*.

### 2. Opening is not an act of its own

5. **The console fuses opening with evaluating**: one action, *Save & evaluate*, and one
   confirmation that states both consequences — what stops being editable, and what the run
   will spend.

6. **`open()` remains a use case and an endpoint of its own.** The fusion is the console's,
   not the domain's. Keeping the HTTP boundary separate is what makes a partial failure
   harmless: a save that succeeds and an open that fails leaves a valid draft, which is
   precisely the state the whole decision exists to make safe. A compound endpoint would
   trade that for one round trip.

### 3. A study is named and described

7. **`purpose` becomes `name`, and `description` is added, optional.** *Purpose* returns to
   the GLOSSARY's meaning and stays unbuilt: the typology is a decision nobody has needed to
   take, and taking it here to justify a column would be building a mechanism with no
   consumer (the argument ADR-0042 used to defer a set of assessors).

### 4. Publishing is signing off

8. **The act, the status, the columns and the event are renamed** — `publish` → `sign_off`,
   `published` → `signed_off`, `published_at`/`published_by` → `signed_off_at`/
   `signed_off_by`, `StudyPublished` → `StudySignedOff`. The rename goes all the way down on
   purpose. A label that disagrees with its model is the same defect this ADR is removing
   from the setup screen, and fixing it in one place while creating it in another is not a
   fix.

9. **`QualityJudgmentPublished` is not touched**, and neither is an instrument version's
   `published` status. Those name other concepts — a judgment being emitted, a norm being
   released — and renaming them for symmetry would assert a kinship that does not exist.

10. **`SCHEMA_VERSION` moves to 3**, because what `compose_report` writes changed: `purpose`
    becomes `name` and `description`, `publishedAt`/`publishedBy` become `signedOffAt`/
    `signedOffBy`. As in ADR-0042 §5 the bump is a signal, not a guard.

11. **The frozen reports that exist are deleted rather than read at two schemas.** This is the
    one clause that costs something ADR-0041 would normally protect, and it is taken with the
    reason stated: the deploy has not happened, so every signed-off report in existence is
    disposable local data, and a dual-shape reader would be permanent machinery guarding
    records nobody holds. **It is a judgement about today, not a precedent.** Once a report
    exists that somebody relies on, this option is gone, and the next change to the document
    must read both shapes — which is what ADR-0042 §5 already required of the frontend and
    what "a report frozen at version 1 is the record it is" already means. The migration's
    `downgrade` restores the structure and says plainly that it does not restore the rows.

## Consequences

- (+) A mis-chosen instrument costs a re-selection instead of a study. The trap that made
  `pin` visible was the strongest argument for the word, and it goes away with it.
- (+) One surface builds a study. The "new study" dialog and the setup card were the same
  form rendered twice with different affordances; they become one component in two states.
- (+) The console's vocabulary and the model's agree at every point that a person reads.
- (−) **A destructive migration.** Signed-off reports are deleted; studies that carried one
  return to `open` and can be signed off again. Everything else — judgments, evidence,
  datasets — is untouched.
- (−) Three CLI commands disappear (`pin-study`, `pin-assessor`, `compose-dataset`) in favour
  of `update-study`, and the runbook's chain changes with them.
- (−) Two event types stop being emitted. An events table read across the change shows
  `InstrumentPinned` rows that no code can produce any more — normal for an append-only log,
  and worth stating because the log is the record of what happened, not of what is possible.
- (−) The pin no longer has a name in the interface, so *where* reproducibility begins is
  carried by one sentence in one dialog. That sentence is now load-bearing.

## Alternatives considered

- **Keep the pins immutable and add an un-pin** → rejected: an un-pin is a re-selection with
  extra ceremony and an extra event, and it makes "pinned once" false in the one place it is
  enforced. The rule is not worth keeping in a state where nothing can rely on it.
- **Leave the domain alone and let the console choreograph declare → pin → pin → compose on
  save** → rejected. It buys the pleasant form and keeps the trap: a draft saved with the
  wrong instrument is still unfixable, and the console would be hiding a defect rather than
  the domain not having one.
- **Rename only the UI labels and keep `published` in the model** → rejected: it recreates,
  in the same commit, the divergence between what the screen says and what the system means
  that this ADR exists to close.
- **"Finish", "Freeze" or "Close" for the final act** → rejected. *Finish* collides with a
  batch run's own `done`, and a study whose run finished is not a study that is finished.
  *Freeze* is a metaphor, and it would compete with the dataset being fixed at open — two
  freezings in one flow teach the reader that neither is precise. *Close* is accurate and
  says strictly less than the signature it stands for.
- **Keep both report schemas readable** → rejected only here, and only because no report that
  anyone relies on exists yet. Clause 11 states the expiry.
- **Rename `open` to `evaluating`** → rejected: `open` is accurate, the domain uses it well,
  and a rename with nothing wrong to fix is churn.
- **Build the `purpose` typology now that the word is free** → deferred. Nothing asks for it;
  it would be a column with no reader and a vocabulary with no rule.

## References

ADR-0042 §8 (the second pin — its mechanics are amended here; §9, §10 and §11 stand) and §5
(the `SCHEMA_VERSION` bump as signal, and the defensive read of new keys) · ADR-0041 (the
frozen report is the record, not the reading surface — the argument that the final act adds a
signature and not visibility, and the protection clause 11 spends deliberately) · ADR-0019
(ratification: the check that survives on every selection) · ADR-0040 (a batch is a run — the
`done` that "Finish" would collide with) · ADR-0036 (an option that cannot work is worse than
no option — why the judge list is filtered by ratification rather than by existence) ·
ADR-0017 (discipline depending on institutional memory is not discipline) · 12-define
invariant 1 (the instrument pinned once before opening — amended here for the second time) ·
GLOSSARY (`EvaluationStudy`, whose purpose typology this gives its word back).
