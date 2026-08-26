# ADR-0055 — A campaign is named

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Orchestration

## Context

An `EvaluationCampaign` carries everything about **what it measures** — the instrument version
it pins, the contents in scope, the quorum that completes each of them — and nothing about
**what it is**. ADR-0002 built it that way deliberately: an open, incremental aggregate, config
plus scope, with no field that does not do work.

The console has been paying for the gap ever since. The campaign list prints
`campaign_id.slice(0, 8)` in the column headed *Campaign*, and the detail page's heading reads
`Campaign a1b2c3d4`. Both are the same admission: there is nothing to show, so the identifier
is dressed up as a title. With one demo campaign that is merely ugly. The first reference
campaign is 40 courses across 25 experts, and it will not be the only round — at which point
two campaigns differ, on every screen an admin reads, by a hex prefix nobody can hold in their
head, and the act of assigning a course to a person is performed against a name that means
nothing.

**The same question was already decided one aggregate over.** ADR-0043 gave the
`EvaluationStudy` a required `name` and an optional `description`, on the reasoning that a
round is *read* by its name and that the column holding a title should say so. A campaign is
the human-side twin of that round; the asymmetry is that the study, which nobody outside this
team convenes, is named, while the campaign, which convenes twenty-five people, is not.

## Decision

**A campaign is named. The name is required, it is not an identifier, and it is correctable
for as long as the campaign exists.**

### 1. Required, and derived from nothing

A campaign cannot be opened without a name, and a blank one is refused by the aggregate on the
way in and by a check constraint underneath it — one rule, said in the two places that can
enforce it.

Nothing supplies a default. A name derived from the instrument and the date would be a name
nobody chose, and it would collide precisely where the console needs the distinction: two
rounds of the same campaign, over the same instrument, in the same month. A name that does not
distinguish is the defect this ADR closes, written back in as a feature.

### 2. Not unique, and never an identifier

`campaignId` identifies; the name describes. Two campaigns may legitimately carry the same
name — a round repeated, a scope re-run after a fix — and a uniqueness constraint would refuse
a true statement at the only moment anyone would want to make it. `studies.name` is not unique
either, for the same reason.

Nothing may look a campaign up by its name. Every reference between aggregates, every event
payload and every URL stays on the id.

### 3. Correctable in any status, closed included

The name binds nothing. No policy reads it, no quorum depends on it, coverage does not move
with it, the golden threshold does not consult it. What opening a campaign fixes — the scope,
the instrument version, the quorum (ADR-0002) — does not include it, and so the protection
those things get is not owed to it.

This is the distinction ADR-0054 drew between a **discovery** and a **statement about the
world**: attribution is one-way because the fact was always true and merely learnt late, so
replacing one would overwrite history; a deployment is redeclarable because it is a claim
about right now. A label is neither. It is not a fact about the campaign at all — it is how a
person refers to it — and a record read under a name with a typo in it is a worse record, not
a more faithful one. A closed campaign therefore renames like any other.

### 4. The label is replaced whole, and the act is `CampaignRenamed`

One act carries both fields: the name, required, and the description, optional. It replaces
what was there.

It does **not** use the per-field `UNCHANGED` sentinel of `UpdateStudyDraft`. That machinery
earns its cost where `null` and *absent* mean different things about a study's selection — a
cleared judge is not an unmentioned judge. A label has no such ambiguity: the console edits
both fields in one prefilled dialog and sends both every time. And because every call carries
a name, `CampaignRenamed` is literally true each time it is written, which a partial patch
could not promise — it would write a rename having changed only the description.

The act publishes, though no policy reacts to it, because `CampaignClosed` publishes on the
same terms: inside Orchestration every state change of the aggregate goes to the outbox.

### 5. The description is optional and nothing backfills it

ADR-0043's rule for the study, unchanged: an absent description is absent. No default is
derived from the name, the scope or anything else.

### 6. The evaluator does not see it

The name is the admin's instrument for telling rounds apart. An assignment is a course and an
instrument; which campaign produced it is not something the evaluator acts on, and putting a
campaign's name — often the round's purpose, sometimes the cohort it compares — on the screen
where somebody judges a course would tell a rater something about the provenance of what they
are judging. That is the neighbouring rule ADR-0053 already protects on the other side. The
name stays in the admin console.

## Consequences

- **Existing rows are backfilled with `Campaign <first 8 of the id>`.** That is not an
  invention: it is the string the console has been displaying for those campaigns all along,
  promoted from a rendering accident to a stored value somebody can now correct.
- **`CampaignOpened` gains `name` and `description` in its payload.** Rows already in the
  outbox keep their shape and are read as the record of what happened, which is what ADR-0043
  did with the events it retired.
- **`CampaignProgressDTO` does not carry the name.** It is Orchestration's published language
  towards Golden Dataset, and a label is not progress; the console reads the name from the
  campaign itself.
- **The demo campaign is named, and its name becomes the key of `seed:demo`'s idempotence** —
  a truer statement of *the same campaign* than the instrument plus the content set it
  compared before, and one more decided act the local setup replays (ADR-0045).

## Alternatives considered

- **A nullable name, with the console falling back to the id.** Leaves the defect in the model
  and spreads it: every surface carries the fallback forever, and two unnamed campaigns are
  again indistinguishable — which is the whole complaint.
- **A unique name.** Refuses a true statement (§2), and buys nothing: nothing looks a campaign
  up by name.
- **A name fixed at open, like the instrument pin.** A typo would then outlive the campaign or
  force a new one over a scope that already has assignments and submissions against it. The
  pin protects reproducibility; a label reproduces nothing.
- **A separate act for the description.** Two endpoints for one dialog, and a second spelling
  of the same edit.

## References

ADR-0043 (a study is named and described — the precedent this follows, including *nothing
backfills a description*, and the `UpdateStudyDraft` sentinel this deliberately does not
inherit) · ADR-0002 (the open campaign: what opening fixes, and what it therefore does not
protect) · ADR-0054 (a discovery is one-way, a statement about the world is redeclarable — the
pair this places a label beside) · ADR-0053 (what a rater is not told about what they judge) ·
ADR-0045 (the local setup replays decided acts) · GLOSSARY (`EvaluationCampaign`).
