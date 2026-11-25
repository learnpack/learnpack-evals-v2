# ADR-0070 — Measuring opens as a guided flow, on a local setup

**Status:** accepted · **Date:** 2026-11 · **DDD context:** cross-cutting (console)

## Context

`/admin/measure` is the console's door to the repository's main job: bring in what a generator
version wrote and measure it. It was built as one long page in three stretches: declare,
scan and register, then the study form mounted underneath. Every field is visible at once.
That was a deliberate choice, recorded in a working note rather than an ADR: the stretches are
numbered because the order is real, and nothing blocks, so the page informs rather than
gates.

The choice served a reader who already knows the model. It does not serve one who does not.
Before that reader sees a result, the page asks for about fourteen decisions, from the package
format to the briefs of the dataset. With the workbench seeded (ADR-0045), most of them have
one valid answer or a safe default. The one decision with real consequences, which assessor
measures the courses, is presented as an identifier.

Three things bound any simplification:

- **ADR-0024.** The generator link is declared, never defaulted. Silence is not a declaration.
- **ADR-0042.** A study's result is the triple of dataset, instrument version and assessor,
  so those are the choices that make two studies comparable. The study form already
  declines to preselect the instrument or the assessor, even when a caller could
  (`components/admin/study-form.tsx`). No ADR states that as a rule; this one does, for the
  console (clause 2). The CLI's `measure` derives the pair when the derivation has exactly
  one answer (`backend/README.md`): a script names what it wants in its arguments, and a
  reader at a screen is better served by seeing the choice.
- **ADR-0035.** Importing from a folder exists only under a local setup. Its endpoints do not
  exist in a deployed console.

## Decision

**On a local setup, `/admin/measure` is a guided flow of three steps: the folder, how thorough
the measurement is, and the start. The long page stays, one link away, as the view with every
option.**

1. **Three steps, each asking one question.** *Folder*: which courses, and which generator
   version made them. *How thorough*: which instrument and which assessor. *Start*: confirm
   and run. A step is answered before the next one opens, because each answer narrows the
   next: an assessor is offered only if it has ratified the chosen instrument, and an
   instrument only if it binds the courses' format.
2. **What has consequences is asked explicitly, never preselected.** This applies ADR-0024
   to the generator, and makes it this ADR's own rule for the two choices ADR-0042 says define
   a result:
   - When the scanned packages declare which generator version made them, the flow asks the
     reader to confirm it, with *Yes*, *Choose another* and *Unknown*. Nothing is chosen
     until the reader answers, and the flow does not continue until then. A version the
     packages declare that is not registered yet is registered only by the reader's own
     click, and the button says so.
   - The instrument and the assessor are chosen by the reader, each on its own, even when
     only one of them is eligible.
   - The start is confirmed in a dialog that names what becomes fixed and what it costs.
3. **What has a safe default is folded away.** The course version (`1`), whether a person
   edited the courses (`unknown`) and, when several are declared, the source root go under
   *More options*. They keep their defaults until somebody opens the section and changes
   them.
4. **An assessor is described by what it does, not by its name alone.** The flow shows how
   many of the criteria the courses' format can supply it decides, and whether it calls a
   model and so spends calls. The numbers come from the assessor's declared coverage and from
   what the format can supply, the same data the study form reads. Step 3 warns when the
   version also has courses in a format the chosen instrument does not read.
5. **The flow tells the reader when it cannot go on.** The flow composes a study that names
   the one generator version it measures, and such a study leaves out courses whose
   generator is unknown (ADR-0044 §6). So courses declared *Unknown* can be registered here
   but not measured: the flow says so and stops after registering them. Courses with no
   brief cannot enter a study either, and the flow says how many are left out. Courses whose
   packages declare a different generator version from the one answered are skipped, and the
   flow says how many.
6. **Local only.** The flow uses the scan endpoints of ADR-0035, so it exists only where they
   do. A deployed console keeps its two screens, *Courses → Add course* and *Studies → New
   study*, and its home sends *Evaluate a batch of courses* to the second.
7. **The long page stays, at `/admin/measure/all`.** It is the view for a reader who wants
   every option in front of them: row-by-row selection, attribution of an already registered
   course, a description for the study. Both views run on the same import and save logic, so
   they cannot disagree about what an act does.

## Consequences

- (+) A reader who does not know the model can measure a batch by answering three questions,
  and is shown what each assessor will and will not decide before choosing it.
- (+) Nothing comparable is ever chosen for the reader: the generator, the instrument and the
  assessor are each one explicit act.
- (−) Two views of one job. They share their logic, so the cost is mostly in the screens:
  a change to what the job asks has to be shown in both.
- (−) The flow registers every course the scan marks as new that does not contradict the
  declared generator, decided when the reader continues. Row-by-row selection stays on the
  long page.

## Alternatives considered

- **Keep the long page as the default and add explanations to it.** Rejected: the problem was
  never that each field lacked a hint. It was that all of them were visible at once, and most
  of them did not need answering.
- **Preselect the instrument and the assessor when only one is eligible,** as the CLI does.
  Rejected for the console: whether a choice is the only one available is a fact about
  today's workbench, and the study would record it as though somebody had made it. The CLI
  keeps its derivation, because there the arguments are the choice.
- **A deployed version of the flow.** Rejected for now: the scan endpoints exist only under
  ADR-0035. A deployed console registers courses one by one, by URL, on *Courses → Add
  course*. A batch intake that does not read the server's disk (zip upload or stored
  packages, ADR-0027's second stage, which ADR-0035 leaves deferred) is what a deployed flow
  would need first.

## References

ADR-0024 (the generator link is declared) · ADR-0035 (local sources, the scan, the mount) ·
ADR-0042 (a study's result is a triple) · ADR-0027 (package intake, and its deferred second
stage) · ADR-0044 §6
(a study names the versions it measures) · ADR-0045 (the seeded workbench) · ADR-0069 (the
console's words).
