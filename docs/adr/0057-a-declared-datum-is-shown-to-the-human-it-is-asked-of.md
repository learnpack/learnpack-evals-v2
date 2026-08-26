# ADR-0057 — A declared datum is shown to the human it is asked of

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Orchestration ·
Content Profiling · Pedagogical Evaluation

## Context

ADR-0053 settled what happens when a course declares nothing an item asks about: the item is
not put to the rater, and the value is derived. It said nothing about the other case, because
nobody had looked at it. **When the course does declare it, the rater is still not shown it.**

The evaluation screen is an iframe of the deployed course and the form. `get_declared_data`
is fetched only to compute the withheld set; its values never leave the backend. So the
rater's whole evidence is whatever the deployed reader happens to render.

**Four of the twelve items cannot be answered that way.** Item 1's own guidance asks the rater
to judge *how the objectives are worded* — *"Agree if every goal the course states names an
action you could watch a learner perform… Disagree if it states its goals in terms you could
not check, such as 'understand'."* Someone who cannot read the objectives is not in a position
to disagree; they are in no position at all. Items 3 and 4 ask them to check coverage and
assessment **against that list**. The declaration lives in the package (ADR-0017); the rater
reads the deployment (ADR-0052 §6); and where those two surfaces differ, four items fall in
the gap with nothing saying so.

**Item 2 shows the damage in a second form.** Its quality is defined as *"The course starts at
a point reachable from the audience's **declared background**"*, but the item asks *"The
course states who it is for…"* — whether a declaration exists. The item was written to fit
what a rater could see, and drifted from the quality it is the only elicitation of.

## Decision

**The rater is shown the declared value of every datum an item they are being asked rests on
— that datum, and nothing else.**

### 1. The rubric is the bound

Each item declares `required_data`. That list already decides whether the item is asked
(ADR-0053); it now also decides what is shown. Today that is `learning_objectives` and
`target_audience`, and it cannot grow without somebody declaring it in the instrument, which
is where such a decision belongs.

The bound is not decorative. The profile also holds `lesson_bodies` — the entire course text —
along with the lesson inventory, the assessment offerings and the concept coverage. "Show the
rater the profile" would replace the course with an extraction dump and quietly make the panel
an auditor of the adapter. *Show what an asked item rests on* cannot become that.

### 2. Asked implies declared

`withheld()` retains an item exactly when its datum is `absent` or the format cannot express
it. So wherever a profile exists, an asked item's datum **is** declared: there is never an
empty panel, and never a value on screen for a question nobody was asked. Where no profile
exists nothing is withheld, every item is asked and nothing is shown — ADR-0053's *an unknown
fact is not an absent datum*, untouched.

### 3. This is not layer 2, and it does not become it

ADR-0015 §1 has the panel judging *"outside instrument execution, without a profile"*, and
reserves work **on** the profile for layer 2, where a human verifies a quoted outcome (*"the
system says there are no objectives; here is the extraction — correct?"*). **This amends §1
and stops there.** What the rater receives is the course's own words, to be judged. They are
never asked whether the extraction is right, and nothing on the screen invites that question:
no provenance, no adapter, no adapter version, no extraction status, no generator. ADR-0053's
blindness rule stands exactly as written.

The distinction is the act, not the data. A rater asked *is this correct?* is verifying. A
rater asked *are these objectives observable?* is judging the course, with the course in
front of them.

### 4. Only what a person can read

The value crosses the API only when it is a string or a list of strings; anything else is
omitted. The rule lives in the contract rather than in a rendering branch, so no screen ever
has to decide what to do with a shape nobody designed for a reader. The cost is stated:
a future structured requirement is invisible to the rater until somebody decides how it
should read, and that is the right place for the decision.

### 5. Item 2 asks what its quality asks

Corrected in the same act, because showing the declaration is what makes the correction
possible — and, left alone, would make its first half answer itself:

> **The course fits the audience it declares, and assumes only what that reader would bring.**

`criterionId`, `dimension`, `qualities` and `requiredData` are unchanged: this is the same
elicitation of the same quality, finally asking it. The window is the one ADR-0056 §1 names —
a published version freezes at its first reference campaign, and none has run.

## Consequences

- **Four items become answerable.** Their coefficients stop depending on whether a deployed
  reader happens to render a metadata field.
- **The two surfaces still differ, and the gap is now narrower, not closed.** A course whose
  package declares nothing while its processed deliverable states its objectives is still
  withheld and still derived — deliberately, because the measurement is of the generator
  (ADR-0023 §2).
- **The screen says more about a course than it did.** It says only what the course says
  about itself, and only where an item asks; but a rater who reads a declaration the pages
  never show is being told something the learner is not. That is the price of asking them
  about a declaration at all, and it is paid knowingly.
- **Item 2's answers are not comparable across the wording change** — there are none to be
  incomparable with, which is why it is done now and not later.

## Alternatives considered

- **Show the whole profile.** Rejected in §1: it makes the panel an auditor of the adapter and
  buries the course.
- **Show nothing and let the rater answer from the deployed course.** The status quo. It reads
  item 1 as *is it visible?* when its guidance asks *is it well written?*, and quietly turns
  an unanswerable item into a disagreement.
- **Drop `target_audience` from the display and keep item 2 as it stands.** Preserves the item
  at the cost of leaving unresolved the one case that prompted the work.
- **Attach each datum to the item that rests on it.** The data appears at the moment of
  judgment, which is better; rejected for now because the objectives would repeat under three
  items in a 460px column. The block carries a pointer on those items instead.

## References

ADR-0053 (an undeclared datum is not asked of a human — this is its other half, and its
blindness rule is unchanged) · ADR-0015 §1 (amended: the panel may read a declaration; §2's
layer 2 is untouched) · ADR-0052 §3 and §6 (the guidance's two halves; the panel judges the
deployed deliverable) · ADR-0017 (the declared surface is the package — why the two surfaces
can differ) · ADR-0009 (a profile entry carries its quote; without it, it is not evidence) ·
ADR-0056 §1 (the window a published version closes) · `pedagogical-reference.yaml`
(`progression-starting-point`, the quality item 2 drifted from).
