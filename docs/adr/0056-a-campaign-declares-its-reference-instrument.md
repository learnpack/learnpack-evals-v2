# ADR-0056 — A campaign declares the reference instrument it pins

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design ·
Evaluation Orchestration

## Context

Opening a campaign from the console has never involved a choice. The form sends
`INSTRUMENT_VERSION_ID`, a string compiled into the frontend, and the campaign pins whatever
that string happened to say on the day. Which reference instrument a campaign judged against
was therefore a fact **nobody chose and nobody could see**.

It went wrong exactly as an invisible constant does. ADR-0052 replaced the seeded reference
with `learnpack-pedagogical-v2` and left the console naming v1; from then until it was
noticed, every attempt to open a campaign answered `rubric version must exist and be
published` and nothing said why. The value is corrected. The assumption underneath it — that
there is one published reference version, and that the console knows which — is not.

**And that assumption was never the design.** The GLOSSARY already settles it: the reference
instrument's stability *"is honoured by **versioning** it: from its first reference campaign,
a version is frozen."* Stability is a property of a published version, which is immutable —
not of the set of them. v2 over v1 is that rule working, and `python -m app.cli seed --file
<path>` takes any rubric JSON, so a second published version can exist in the store today.
Nothing in the console could reach it.

The reference instrument also has **no read surface at all**: `RubricQueries` exposes only
`get_rubric(id)`. Nothing can list what the store holds, which is why a constant was the only
option available to the form in the first place.

## Decision

**A campaign declares which version of the reference instrument it pins, chosen from the
published ones, and the console says which one it was.**

### 1. The choice is made when the campaign opens, and only then

What a campaign fixes on opening — its scope, its quorum, its instrument (ADR-0002) — stays
fixed. ADR-0055 let the **label** be corrected at any time on the grounds that a label binds
nothing; this binds everything. Judgments already submitted answered *this* version's items,
on its scale, in its response format. There is no endpoint that changes it, and adding one
would silently reinterpret answers people already gave.

### 2. Only published versions are offered

`open_campaign` already refuses a version that is not published, with 422. A picker listing
drafts would be offering a failure — ADR-0036's rule, the one that filters the study's judge
list by ratification rather than by existence.

### 3. The reference instrument gets a read surface of its own

`GET /admin/reference/instruments`, beside `/admin/reference/qualities`.

**Not** under `/admin/instruments`. That path serves `instrument_versions` — the automated
evidential argument of ADR-0012–0014 — and the reference instrument is a different artifact
that survives under a shared word (GLOSSARY: *"a slice 1 term that the Instrument supersedes;
the human reference instrument survives under it"*). Returning both kinds from one endpoint,
told apart by a type field, would save a route by making the console's own vocabulary lie.

### 4. The list is a summary, not a snapshot

Identity, name, version, scale, response format and how many items — what somebody needs to
tell two versions apart. This departs from `list_instruments`, which returns whole snapshots:
a dropdown does not need twelve items of guidance text per option in order to be chosen from.

### 5. This decides nothing about comparability

Two campaigns pinned to different reference versions produce human scores over different
items, possibly on a different scale and in a different response format. Whether those can be
read together is a reporting question — ADR-0006's dispersion does not answer it and neither
does this. What changes is only that the question becomes **askable**: the version each
campaign pinned is now a choice somebody made, recorded and visible, instead of a constant
nobody read.

## Consequences

- **`INSTRUMENT_VERSION_ID` is deleted.** The class of failure it produced — a seed installing
  an id the console does not know about — cannot recur, because the console now reads what the
  store holds instead of asserting what it should hold.
- **A store with no published reference version says so in the form**, where the choice is
  made, rather than failing at submit with the router's sentence.
- **The `STATUS.md` entry this replaces goes.** What stays open is comparability (§5), and it
  is recorded as such.
- The campaign's own module is untouched: `OpenCampaignRequest` already carried the id and
  already validated it. This decision is about who chooses it.

## Alternatives considered

- **Keep a constant, corrected.** Puts the same rot back: the second version stays
  unreachable, and the next seed that moves the id breaks the form mutely and completely.
- **Extend `/admin/instruments` to return both kinds.** One endpoint over two artifacts,
  distinguished by a discriminator — see §3.
- **Let a campaign change its instrument after opening.** See §1: it would reinterpret
  submitted judgments.
- **Offer drafts, disabled, so an admin can see what exists.** The campaign form is not where
  the instrument catalogue is browsed, and a disabled row answers a question nobody asked
  there.

## References

ADR-0015 §3 and ADR-0052 (the reference instrument, and the v1 → v2 that made the plural
real) · ADR-0002 (what opening a campaign fixes) · ADR-0055 (a label is correctable *because*
it binds nothing — the contrast §1 rests on) · ADR-0036, via ADR-0043 (an option that cannot
work is worse than no option) · ADR-0012 (the instrument lifecycle `/admin/instruments`
serves) · GLOSSARY (*Rubric / reference instrument* against *Instrument / InstrumentVersion*,
and stability honoured by versioning).
