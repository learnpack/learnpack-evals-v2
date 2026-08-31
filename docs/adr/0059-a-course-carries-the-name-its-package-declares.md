# ADR-0059 — A course carries the name its package declares

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry ·
Evaluation Orchestration

## Context

An evaluator who opens their pending work reads `Course 3f9a1c02`. The string is
`content_id.slice(0, 8)` — eight characters of a UUID dressed up as a title, the same
admission ADR-0055 found in the campaign list, on the one screen this system puts in front of
somebody outside the team. Beneath it the card prints the instrument version id, which is our
coordinate for the questionnaire and not their task. The evaluation screen itself names
nothing at all: a person is handed an iframe and asked to judge what is in it.

The console is no better off. Wherever a course is listed, picked, assigned or diffed, the
column headed *Course* holds `externalId`. For LearnpackV1 that is the package slug; for
LearnpackV2 it is `<seed>-<run start>`, which ADR-0027 made an identifier **on purpose** —
it says which instruction produced the course and which run of it, and it survives the tree
being moved or renamed. It was never meant to be read as a name, and a dataset of forty
courses named that way cannot be read at all.

**The name exists, and the registration throws it away.** Mechanical discovery already reads
it: `DiscoveredPackage` carries a `title` beside the external id and the content hash, filled
from `learn.json`'s `title` for LearnpackV1 and from the lesson plan's `course_title` for
LearnpackV2. Its only consumer today is the local scan preview, which shows a candidate
before anybody registers it. The moment the course is registered the title is dropped:
`EducationalContent` has no field for it, `contents` no column, `ContentSnapshot` no key. So
this is not a new fact about a course. It is the fact discovery already reads, kept.

## Decision

**A registered course carries the title its package declares. It is discovered, never typed;
it names the course wherever a person reads one; and the identifier stops standing in for it.**

### 1. Discovered, never authored

The title is read off the package by the format's discovery, exactly like `externalId` and
`contentHash`. No hand path accepts one: not the registration endpoint, not the CLI, not a
later correcting act. There is no `RenameContent`.

This is not fastidiousness. ADR-0017 retired content metadata so that contamination of the
declared surface would be *impossible by construction* — there is no channel where a human
hand or an external AI can declare on behalf of the course. A title somebody typed would be
exactly that channel, reopened for the most quotable field there is. A title discovery read is
the package speaking, which is what ADR-0017 protects.

### 2. `externalId` identifies; the title describes

Neither replaces the other — the distinction ADR-0055 §2 drew for a campaign.
`(packageFormat, externalId, version)` remains the logical identity, the key of every
reference, every event payload, every CSV somebody exports and every command they type.
Nothing is ever looked up by title, and no uniqueness is asked of it: two courses generated
from one commission legitimately declare the same one, and in a comparison dataset that is the
normal case, not the exception.

The console therefore shows both — the title as the name, the `externalId` beside it — and
sorts by what it displays.

### 3. Null is honest, and only the console falls back

A package that declares no title, and every course registered before this column existed,
carry `NULL`. Nothing invents one from the slug: a name derived from an identifier is the
defect this ADR closes, written back in as a feature.

The console falls back to `externalId`, which is what it displayed all along. The evaluator's
screen does not — see §5.

### 4. It is not a declared datum

The title names what the evaluator is about to open. It is not evidence, no criterion rests on
it, and it does not enter the panel of what the course declares about itself: ADR-0057 §1's
bound holds, and what is shown there is still decided by an item's `required_data` and by
nothing else.

The profile does hold a title, inside `course_descriptor`, and it stays there. That entry is a
record with a citation and an adapter version, minted so criteria can judge what a course
claims about itself; ADR-0057 §4 already keeps it off a rater's screen because a record is not
a shape a person reads. A label and a datum are not the same thing even when they are the same
string.

### 5. What the evaluator's screen carries, and what it does not

It carries the course's title and a short opaque reference — the first characters of the
`contentId`, which is what somebody quotes when a course will not load. It carries neither
`externalId` nor the instrument version id.

`externalId` is refused on the rule ADR-0052 §7 states and ADR-0057 §3 enumerates: the panel is
blind to which generator produced what. A LearnpackV1 slug can name the generator outright,
and a LearnpackV2 id names a run. The title cannot leak what the slug leaks, because it is the
course's own words about itself and the rater reads it inside the course a moment later.

The campaign's name stays out too, and that is ADR-0055 §6 unchanged, not an oversight: which
round produced an assignment is often the round's purpose or the cohort it compares, and the
evaluator acts on none of it.

### 6. The registry stores it, and does not read it from the profile

The alternative was to leave the title where it is already persisted — `course_descriptor` in
Content Profiling — and have the console join. It loses on two counts. A course is registered
before it is profiled and can be listed, picked into a dataset and assigned in between, so the
name would appear late and for reasons nobody could see. And a profile can fail: a rater's
screen would then be unable to name a course because an extraction adapter could not read some
other part of the package.

The registry already stores what discovery read about the course's identity. The title is one
of those reads, and this puts it where the others are.

### 7. Refused for now, so the next reader knows it was a decision

**Renaming**, per §1. **The multilingual title:** LearnpackV1 declares `{en, es}` and
discovery's `_english()` already picks one — the English string is stored, and which language a
rater should read is a question for whoever asks it. **The title in the frozen study report:**
those bodies keep `externalId`, because a frozen report is the record of what was measured and
not a reading surface (ADR-0041), and the reporting and profiling read models keep it for the
same reason — each would need its own column, and none of them is where a person meets a
course.

## Consequences

- **Migration `0032` adds one nullable column and backfills nothing.** A null there is a true
  statement — this course was registered before the title was kept, or its package declares
  none — and a migration that guessed would make it a false one.
- **`backfill-content-titles` recovers what the profile already holds.** For a course
  registered before this decision, the title is read from `course_descriptor` — the same bytes
  discovery would have read — and written once. It has no author, publishes no event and
  writes nothing about who ran it: nothing about the content changed, the row is catching up
  with what its package always declared. It is a migration that happens to need a profile, and
  running it twice fills nothing the second time.
- **`ContentVersionRegistered` gains `title` in its payload**, on the rule the event module
  already states: a payload that needs a join against current state to be read is a worse
  record. Rows already in the outbox keep their shape.
- **A course registered by hand is named only if its package can still be read.**
  Registration types an identity and never a name, but what fills the column afterwards is
  the profile, and a hand-registered version whose artifact list points at a real package
  profiles like any other. What stays unnamed is a version registered with no artifacts, one
  whose extraction fails, or one whose format declares no title — and for those there is no
  act, which is §1 rather than a gap in it.
- **The evaluator's list gains a name and loses two identifiers**, so a rater with several
  assignments can tell them apart by what they are rather than by a hex prefix.

## Alternatives considered

- **A `title` the console can edit.** Reopens the metadata channel ADR-0017 closed, for the
  field most likely to be tidied up, on courses whose whole point is to be judged as the
  generator emitted them.
- **Reading the title from the profile at display time.** §6: late, and it fails with the
  extraction.
- **Falling back to `externalId` on the evaluator's screen.** The cheap fallback is exactly
  the leak §5 refuses.
- **Backfilling the column inside the migration.** It would have to read another module's
  table from a registry migration, and could never be run again for a course profiled later.
- **Leaving the frozen report and the other read models to catch up in the same change.** Each
  carries its own copy of `externalId` for its own reason; conflating them with the live
  surfaces would freeze a label into a record that is meant to be immutable.

## References

ADR-0027 (package intake by mechanical discovery — where the title is already read, and why
LearnpackV2's `externalId` is an identifier by design) · ADR-0017 (the declared surface is the
package; the retired metadata channel §1 refuses to reopen) · ADR-0055 (a campaign is named —
the same defect one aggregate over, its *identifies vs. describes* distinction, and §6, which
keeps the campaign's name off the evaluator's screen) · ADR-0052 §7 (the panel is blind to
which generator produced what) · ADR-0057 §1 and §4 (what an item's `required_data` bounds, and
why a record never reaches a rater) · ADR-0053 (an unknown fact is not an absent datum) ·
ADR-0041 (the frozen report is the record, not the reading surface) · ADR-0024 and ADR-0054
(the two acts that change a registered course — the title is neither) · GLOSSARY
(`EducationalContent`, `ContentVersion`).
