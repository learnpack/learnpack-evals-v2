# Calibrating an instrument

This is the guide for one job: a criterion is not measuring what you meant, or does not exist
yet, and you want to find out what it should ask before writing it. It assumes no familiarity
with the rest of the repository.

The other runbook, [measuring what a generator produced](RUNBOOK-measuring.md), is the
opposite job: an instrument you trust, run over courses to get a score. Come here when it is
the instrument you no longer trust.

## What this gives you, and what it does not

You get **evidence about the question**, never a verdict about a course. Four tools:

- a **trace** of every prompt and answer, to see what was actually asked;
- **repeats** of one course, to separate a criterion whose threshold is unwritten from a judge
  that cannot read;
- two **calibration dumps**, which build the raw material a criterion would consume and hand
  it to you as a table to mark up;
- **`evaluate --dry-run` over drafts you know the answer for**, which is how a change to a
  criterion that already executes gets tested before it is shipped — and what the numbers to
  read are is *A correct verdict is not a safe one*, below.

There is a second way into this job, and it comes from outside. When a campaign of experts has
read the same courses an assessor judged, the **Validity** section of a study report says how
much each claim follows the panel, and a claim that does not follow it names the courses where
the two sides read the same course differently — the experts' answers and comments beside the
passage the assessor cited. Each of those courses links straight into this console with the
course and the criterion already loaded. The evidence a run gives you here is the same either
way; what the panel adds is external evidence that the pair measures what it says it measures,
which no amount of repeating a run can supply.

Two cautions that belong to that entrance. **Read the check before the judge**: a criterion
whose threshold was never written makes every assessor look equally bad, so starting at the
prompt chases ghosts. And **a course from the campaign must not become an example inside a
prompt** — once it has been shown the answer it leaves the sample, because it can no longer
test the version it was rewritten from.

You do **not** get a pass or a fail from any of it, and that is deliberate. Nothing here
writes a judgment, enters a report, or reaches the fitness projection. The dumps in particular
are outside the assessor's identity (ADR-0034): no executor imports them, no criterion is
answered from them, and editing them costs nobody a ratification. What they produce is a
proposal to change the instrument, which then goes through the ordinary acts — bump, publish,
ratify.

## Before you start

The dumps read a **profile**, so the course has to be registered and profiled first (see the
measuring runbook), the database has to be up, and `LLM_API_KEY` has to be set. Everything
here runs from `backend/`.

```bash
docker compose up -d              # the dumps read the profile out of the database
uv run python -m app.cli dump-concept-map --content-id <uuid>
```

Set `LLM_TRACE_DIR` before any of it if you want the prompts on disk. You almost always do.

---

## Dump 1 — what each lesson does with the course's concepts

```bash
uv run python -m app.cli dump-concept-touches --content-id <uuid> [--out runs/concept-touches]
```

One call over a profiled draft, one row per place a lesson deals with a concept **another**
lesson declares, out as a markdown table and the same rows as JSON.

What each row carries, and which half of it came from where:

| From the model | From the plan and the text |
|---|---|
| `mode` — `uses_as_known` · `re_explains` · `points_at` | `direction` — `earlier` · `later` · `own` |
| `newness` — `new_context` · `same_as_taught` · `n_a` | `distance`, in lessons of the declared order |
| the verbatim `quote` | `zone` — `opening` · `middle` · `closing` |

The split is the point. **Two axes rather than one** because a single "does this lesson apply
an earlier concept?" fuses what the lesson does with how new the work is, and a reader who
disagrees with where that line sits cannot move it without buying another run. **`direction`
and `distance` are computed, never asked**: where a concept is taught is a fact of the plan,
and an answer allowed to carry it would be free to move a concept in time. And **`zone` is
measured against 1200 characters at each end** — the window an adjacent-pair task would read —
so "how many backward references sit outside the opening" is answerable against the design
that would have to catch them.

The last column of the table is **empty on purpose**: `mode` and `newness` are what the model
saw, `your call` is where the bar actually goes, and the two side by side are the only
measurement of the distance between them that exists.

**What it is good for.** The per-touch geometry — how far back a reference reaches and where
in the lesson it sits — which no other tool produces. That is what tells you whether a
criterion framed over adjacent pairs could ever catch the references a course actually has.

**What it is not good for.** Deciding where a concept is introduced. It takes the plan's word
for that, and the plan can be wrong (see below).

---

## Dump 2 — where each concept is stated, developed, used and checked

```bash
uv run python -m app.cli dump-concept-map --content-id <uuid> \
    [--shape whole|per_module|two_phase] [--out runs/concept-map]
```

The same corpus asked the other way round: one entry per concept, with the lessons that deal
with it sorted into five groups.

| group | the lesson… |
|---|---|
| `defines` | says **what the concept is** |
| `develops` | says **more about it** than what it is — why it matters, what follows, where it stops applying |
| `uses_as_known` | **does something with it**, treating the reader as already having it |
| `assessed` | sets a task that **checks** it |
| `mentions` | **names** it and nothing else |

Three properties are worth knowing before you read a table.

**Every group is a local act.** `defines` asks only whether a lesson says what the concept is,
never which lesson introduces it. Which appearance is the introduction is `min(position)`,
computed afterwards — so a concept may be stated by several lessons, and that is not a
contradiction but a finding: the first is the introduction and every later one is the course
stating again what it had already stated. The table marks those `(again)`.

**A lesson may appear in more than one group** for the same concept. A lesson that states what
a concept is and also says more about it belongs in both; so does one that works with a
concept and sets an exercise on it. Forcing one slot per lesson was measured and it collapses
`develops` to almost nothing.

**The plan is never shown to the model.** It gets bare concept names and works out from the
text where they are stated. The plan's own concept-to-lesson assignment is joined onto every
row afterwards, in the `plan declares it in` and `here?` columns. **A `defines` row whose
`here?` is empty is the plan and the prose disagreeing about where a concept is taught** — a
defect no criterion can see, because criteria consume the data requirement rather than audit
it.

### Which shape

`whole` asks everything in one call. `per_module` fans out, one call per module. `two_phase`
asks where each concept is stated over the whole course, then what each module does with it,
module by module.

Start with **`whole`**: measured against two independent readers of one draft it agreed with
them as closely as they agreed with each other, and it is the cheapest. Reach for the others
when the whole-course call under-reports `uses_as_known`, which it does on larger drafts —
`per_module` roughly doubles what it finds there, at a cost in the definition anchor.

### Reading it

Read the `## What the answer did not yield` section at the bottom **before** concluding
anything from an absence. A row is dropped rather than the answer refused whenever the loss is
one row — a quote that will not ground, a lesson nobody asked about, a duplicate — so silence
in the table can mean either "the course does not do this" or "that touch was unusable", and
only that section tells the two apart.

Four things fall out of a table for free, none of which any current criterion reports:

- a concept **no lesson ever states**;
- a concept stated **twice** — the course starting over rather than building;
- a concept **used before it is stated**;
- a concept that is stated and **never used or checked** again.

---

## Which dump for which question

| you want to know | use |
|---|---|
| where a concept is introduced, and whether the plan agrees | dump 2 |
| whether later material puts earlier material to work | dump 2 |
| whether assessment reaches back | dump 2 |
| how far back a reference reaches, and where in the lesson it sits | dump 1 |
| whether a pairwise or windowed criterion could catch what exists | dump 1 |

## Run it more than once, and never read a count as a measurement

Neither dump has a vote or a threshold to average out a bad draw. Two runs of one draft at
identical settings have produced 40 touches and 29, agreed on the fine classification for half
the touches they shared, and cited the same passage for under a third of them. Some of that is
benign — a lesson can deal with a concept in two places and both citations are true, which
also means a classification compared across two different sentences is not really a
disagreement about the same thing.

What follows for reading is the same either way: **take the union of the runs as the rows
worth judging, and treat how often a row recurs as part of what you are judging.** A category
that appears in one run and not the next is telling you the question is underspecified, which
is exactly what these dumps are for.

**Reasoning effort is not a cost knob here.** A lower effort still holds the output contract
and runs four to five times faster for a quarter of the output tokens — and stops using some
of the finer categories almost entirely. A cheaper run that collapses the axis a bar gets set
on is not cheaper at anything that matters.

## Reading a calibration trace

A semantic criterion's verdict is only as good as the question that produced it, and the
question is a prompt nobody sees. `LLM_TRACE_DIR` is where every attempt gets written —
one JSON object per line, per run:

```
{"task_id": "...", "attempt": 1, "model_requested": "...", "model_answered": "...",
 "provider": "...", "sampling": {...}, "messages": [...], "response_text": "...",
 "finish_reason": "...", "tokens_in": 0, "tokens_out": 0, "latency_ms": 0, "error": null}
```

One record per **attempt**, not per successful call: a task that took three rounds to
satisfy its output contract wrote three lines, and the second line's `messages` end with
the validator's own complaint about the first. Nothing is truncated — an abridged prompt
cannot be compared against the one that produced a different answer, which is the only
reason to read this.

What each field settles:

- `sampling` — what was asked for besides the conversation: temperature, the output
  budget, the response format, whether the model may reason. It decides the answer as
  much as the prompt does, so it is recorded next to it; `drafts-hybrid:1` failed every
  run on this half with its prompts intact.
- `finish_reason: "length"` with **no content** — the model stopped at the token limit
  having written nothing. A reasoning model bills its thinking as output tokens, so
  `max_tokens` is a budget the thinking can spend entirely; compare `completion_tokens`
  against `completion_tokens_details.reasoning_tokens` in the raw body to see it. The
  remedy is the task's budget or its `reasoning` setting, never a retry — the limit
  produces the same answer every time. This is what `drafts-hybrid:1` lost every run to.
- `provider` — OpenRouter routes one model id to several upstreams, and they differ in
  whether they reason and in how they honor `response_format`, so two runs asking the
  same question can get different shapes back. This is who answered.
- `error` with no `response_text` — the request never landed (timeout, rate limit). The
  next line is the retry.
- `error` mentioning **upstream** — the gateway answered 200 and the provider behind it
  failed. Treated as transient: the next attempt usually lands somewhere else.

Every door writes one: the page's runs under their run id, `evaluate --dry-run` under
`cli-<id>`, the dumps under `touches-<id>` and `map-<id>`, each printing the path when it
finishes. The folder is gitignored and disposable — the traces of a machine, not of the repo.
Leave `LLM_TRACE_DIR` empty and none are written.

## What repeated runs tell you

One trace shows whether a question was answered. Only **repeats of the same content** show
whether the answer means anything, and they are the cheapest diagnostic available: run one
draft three times and compare the verdicts criterion by criterion. Six things that
measurement settles, none of them obvious from a single run.

- **Where the model disagrees tells you whose defect it is.** If repeats quote the same
  passages and describe the same facts, then split on the verdict, the criterion never said
  where its threshold is — and the fix is prose in the instrument, not a better prompt. If
  repeats disagree about *what the text says*, that is the judge, and only then are prompts,
  models or sampling the answer. Read the reasons side by side before touching anything.
- **Writing the missing threshold beats sampling.** Voting reduces variance, and an
  under-specified criterion is not variance: it is two defensible readings of one sentence,
  and a vote just picks one of them more consistently. Fixing the text removes the
  disagreement instead of averaging it.
- **Borderline instances belong to (content, criterion) pairs, not to criteria.** A criterion
  can be unanimous on one draft and a coin flip on the next, and one that looked settled over
  several observations can still turn. So there is no list of "hard criteria" to sample
  selectively — sampling, when it is used, applies to all of them.
- **A judgement is only diagnosable because it is quoted.** Every distinction above comes
  from comparing the passages and reasons of different runs. A bare verdict shows a number
  moving and nothing about why, which is the reason the output contract demands evidence at
  all (ADR-0009).
- **Ask for a transcription only from prose you did not write.** A corpus this system BUILDS
  — objectives beside the tasks that measure them, one entry per line under the same label —
  is a template, and a model asked to copy one line out of twenty near-identical ones splices
  the prefix of one onto the body of another. The grounding check catches it and the run pays
  for it: one campaign spent 9 retries in 21 calls and lost an evaluation that way. Over a
  built corpus, number the entries and ask which one, not what it says; the passage a report
  shows is then fetched from the profile, which is the course's own text rather than the
  model's rendering of our labels.
- **Let the model judge one thing at a time and add the answers up in code.** A criterion
  whose corpus is a set of units (one block per objective, per lesson, per module) invites a
  single verdict over all of them, and then the aggregation is the model's: repeats will name
  different units, pick different failure modes, and occasionally contradict their own reason
  — one answered *"satisfied except obj-3, whose tasks are recognition items"* and voted pass.
  One entry per unit costs no extra calls, and it turns "which unit failed" into data a
  reader can compare across runs.

A judged criterion reports how close its vote was, as a
`judgment_agreement_<task>` metric of `{samples, agreed}`. Treat a criterion that keeps coming
back **2-1 as a bug report about the instrument**, not as noise to average away — that is the
signature of the first case above.

Two more signals ride with every task's `llm_*` metric since ADR-0037. `clean_retries`
counts the fresh conversations an answer cost: verdicts that needed one are a shifted
population — the retry changed the conversation that produced them — so compare them apart
before reading agreement across runs. And a criterion carrying `execution_error` names in
its cause `{task, kind, message}` exactly which task failed and how; a recurring
`degeneration` on one (content, criterion) pair is a bug report about the question, the
same way a recurring 2-1 vote is.

And the limit worth stating: self-agreement is not correctness. A criterion can be perfectly
stable and stably wrong, and nothing in these runs would show it. Only a human reading the
verdicts against the content can.

## The one rule that will bite you

**A model is reliable about coarse, locatable facts and unreliable about which fine category a
fact falls into.** Where a concept is stated, whether a lesson deals with it at all: dependable
enough to build on. Whether the dealing counts as developing it or as using it: not. Build a
criterion on the coarse fact plus a deterministic anchor, never on a fine semantic label.

The corollary is what to do when a dump disagrees with itself between runs. If the runs report
the same places and label them differently, widen what the criterion counts until the label
stops deciding the verdict. If they report different places, that is recall, and no rewording
fixes it.

## A correct verdict is not a safe one

Once a criterion executes, the obvious way to make it cheaper is to ask for less thinking, or
to ask a cheaper model. The concept map is the case: it is one call for definitions plus one
per module for usage, and those usage calls are six of the seven and about three quarters of
the map's output tokens. At high effort most of those tokens are reasoning rather than answer.

That saving has been measured, on two drafts and against a bar of two thirds — one draft
independent readers call cumulative, one they call *"partially"*. Each row is the ratio the
criterion actually computed, `built/of`, not a row count standing in for it:

| usage passes asked at | good draft, within | good draft, across | borderline draft, within | borderline draft, across |
|---|---|---|---|---|
| the strong model, high effort | PASS 8/9 *(needs 6)* | PASS 5/5 *(needs 4)* | PASS 5/6 *(needs 4)* | FAIL 2/4 |
| the same model, medium effort | **PASS 6/9** | PASS 5/5 | PASS 5/6 · 5/6 | FAIL 1/4 · 0/4 |
| a cheaper flash model, medium | PASS 8/9 | **FAIL 3/5** | PASS 5/6 · **4/6** | FAIL 0/4 · 1/4 |

Two different failures, and only one of them looks like a failure.

**The cheaper model broke the good draft outright.** Its across-modules verdict went from 5/5
to 3/5, so both drafts came back with the same pair of verdicts and the criterion stopped
telling them apart — which is the only thing it is for. It was not even cheap: it spent more
output tokens than the strong model at medium and recovered a third of the usage rows.

**The same model at medium got every verdict right and spent the margin.** The good draft went
from 8 of 9 to exactly 6 of 9 against a bar of 6. Nothing was wrong with that run; what is
wrong is that one lesson fewer flips it, on an axis that is known to move — the same draft at
identical settings has produced 54 and 59 usage rows. A pass with no margin on a quantity that
varies between runs is a coin, not a verdict.

**So test a cheaper reading on the draft that should PASS, and read the distance to the bar.**
The instinct is to check that the bad draft still fails, and that is the check it survives for
the wrong reason: recall collapse pushes everything down, which looks like agreement on the
draft that was already failing. The damage shows up first as a shrinking margin on the good
one. Both continuity criteria report `{of, built}` as a metric of every evaluation, so the
margin is already in the record — no extra run buys it.

None of this says medium effort is useless; it says it costs recall, and recall is what a
margin is made of. The definitions pass is the other side of the same coin and is why it is
never lowered: it is the deterministic anchor every one of these verdicts hangs on, and at
medium it drifts to 14–15 of 18 against readers where high scores 17 of 17.

## When something does not work

- **The command refuses with "no ok profile"** — the course is registered but not profiled, or
  profiling failed. `profile-content` or `reprofile` first.
- **It refuses naming a data requirement** — the format's adapter does not supply it. That is a
  fact about the adapter, not a bug here; nothing to do at this end.
- **The run dies at the token budget** — the model spent it on reasoning. Lower the effort or
  raise the budget; retrying spends it on the same answer.
- **A whole run reports almost nothing** — check the trace before believing the course. Some
  model and provider combinations answer in a shape the validator refuses, and the retry that
  fixed the shape can also flatten the answer.
- **Everything hangs with no error** — the database is down.

## Where to look next

- [Measuring what a generator produced](RUNBOOK-measuring.md) — the other job.
- `backend/README.md` — the backend itself: setup, layers, the commands around these.
- `docs/GLOSSARY.md` — what claim, criterion, assessor and instrument mean here.
