# Measuring what a generator produced

This is the guide for one job: you have a folder of courses that a version of a generator
wrote, and you want a score. It assumes no familiarity with the rest of the repository, and
you should not need to read anything else to follow it.

## What this gives you, and what it does not

You get, per course and rolled up over the whole batch, a value between 0 and 1 for each
**quality** the instrument covers (there are 21 in all) and for each of the five
**pedagogical dimensions** they belong to. You also get, beside every value, **what it was
computed over**.

You do **not** get a single overall score, and that is a decision rather than a gap: the
system refuses to publish one, because collapsing five dimensions into one number is a
judgement about what matters, and it is not the measuring instrument's judgement to make. If
your work needs one number, you define how to collapse them — see
[Turning it into one number](#turning-it-into-one-number).

Two words used throughout, because the system uses them:

- A **commission** (`brief`) is the request a course was generated from. The generator writes
  it into the package, and the system reads it from there.
- A **round** (`study`) is one measurement: a set of courses, one instrument version, one
  judge. All three are fixed when the round opens, which is what makes a result reproducible.

## Setting up, once

You need Docker, [Task](https://taskfile.dev/installation/),
[uv](https://docs.astral.sh/uv/) and Node 20+.

```bash
task setup     # from the repo root: containers, dependencies, migrations, workbench
```

Then two lines in `backend/.env`:

```bash
# The folder your generator writes its runs into. `generated` is a name you choose; it
# becomes part of the URL the tree is served at, so pick one and keep it.
LOCAL_SOURCE_ROOTS=generated=/path/to/your/generator/datasets/generated

# An OpenRouter key — the judges are pinned to models served there. Only the assessors
# that carry an LLM need it.
LLM_API_KEY=<your OpenRouter key>
```

A folder declared here is mounted when the API starts, so **adding one needs a restart**.

Finally, start the API and leave it running — the courses are read over http, from a mount
the API serves:

```bash
task backend   # http://localhost:8000
task frontend  # http://localhost:3000, optional but useful for reading results
```

### What the setup left you

`task setup` publishes the instruments, accepts the adapters that read each package format,
ratifies the assessors and registers the generator lineage. You can see all of it at
`/admin/instruments`, `/admin/profiles` and `/admin/assessors`.

To start over from an empty database at any point:

```bash
task db:reset   # destroys the local database and rebuilds all of the above
```

## How your folders have to be laid out

```
<the folder you declared>/
  <generator-name>-<version>/     ← one folder per version you want to measure
    <course>/
    <course>/
```

The name of the middle folder **declares which generator version made those courses**, which
is what a round is about. `learnpack-generator-04a7dd5-dirty` means the lineage
`learnpack-generator` at version `04a7dd5-dirty`; the version can be a commit sha, a tag,
anything — it is matched against the registered lineage, and the rest is the version.

The lineage has to be registered first (`task setup` does it for `learnpack-generator`). A
version that is new is registered as it is read, and printed when it happens. Loose files
beside the course folders are ignored.

## Measuring one batch

```bash
cd backend
uv run python -m app.cli measure --root generated \
                                 --path learnpack-generator-<version> \
                                 --assessor drafts-hybrid > run.json
```

That one command registers every course in the folder, reads each one, opens a round scoped to
exactly that generator version, judges every course, and prints the result.

**Progress goes to the screen and the result goes to the file.** That split is deliberate:
`> run.json` gives you the complete document while you still watch the batch advance.

Two flags you will use:

| Flag | When |
|---|---|
| `--assessor <name>` | required when more than one judge has been ratified for the instrument. `name` alone picks whatever version the code currently carries |
| `--concurrency N` | how many courses at a time. Defaults to `LLM_MAX_CONCURRENCY` (4). |

Everything else is derived: the instrument comes from the package format, the round's name
from the folder, the commissions from the packages.

**Re-running the same command resumes** — courses this judge already scored are skipped — so
an interrupted batch is continued by repeating it. Ctrl-C stops it cleanly: what finished
stays, what was in flight writes nothing, and you still get the summary.

To read the score again later without re-judging anything:

```bash
uv run python -m app.cli show-fitness --study-id <id> > fitness.json
```

## Reading the result

`run.json` has two halves: `batch` (how the run went) and `fitness` (the score).

### The header says what the numbers mean

```json
{
  "studyId": "1944e1e0-9c2d-4da2-8361-4b1d6a9f232a",
  "instrumentVersionId": "course-drafts-qa-v6",
  "formulaVersion": "1",
  "denominatorRule": {
    "numerator": ["pass"],
    "penalizing": ["fail", "no_evidence"],
    "excluded": ["not_applicable", "not_assessed", "execution_error"]
  }
}
```

Every criterion of every course ends in one of six states, and only three of them are in the
arithmetic:

| State | Meaning | In the score? |
|---|---|---|
| `pass` | there is evidence and it satisfies the criterion | numerator |
| `fail` | there is evidence and it does not | denominator |
| `no_evidence` | the package could carry it and does not | denominator |
| `not_applicable` | no adapter for this format can supply the datum at all | **out** |
| `not_assessed` | the judge declares it does not check this criterion | **out** |
| `execution_error` | the run failed on that criterion — a fact about the run, not the course | **out** |

The last three are excluded on purpose: a generator should not be scored for a question
nobody asked. `not_assessed` in particular is **not a zero** — it is the visible backlog of
criteria no judge executes yet.

### Three levels, and one to start from

The document carries the same shape at three levels: `contents[]` (per course),
`generators[]` (per generator version) and `study` (the whole round). Use `study` for a
score, and the other two when a number surprises you.

```json
"study": {
  "dimensions": {
    "objectives-quality":      { "fitness": 0.625,    "coverage": { "qualities": 3, "defined": 2 } },
    "instructional-design":    { "fitness": 0.75,     "coverage": { "qualities": 4, "defined": 2 } },
    "inter-lesson-coherence":  { "fitness": 0.666667, "coverage": { "qualities": 4, "defined": 3 } },
    "learning-progression":    { "fitness": 0.666667, "coverage": { "qualities": 4, "defined": 3 } },
    "constructive-alignment":  { "fitness": 0.0,      "coverage": { "qualities": 4, "defined": 1 } }
  },
  "qualities": { "…": "one entry per quality, each with its own criteria counts" }
}
```

Read `coverage` before the value. `constructive-alignment` above says `defined: 1` of 4
qualities: that 0.0 rests on a quarter of the dimension, and the other three qualities were
not measured at all. A dimension where nothing was measured answers `undefined`, never `0`.

### Where a value comes from

Each course carries its qualities with the counts behind them, so any number can be traced:

```json
"alignment-assessment": {
  "fitness": 0.0,
  "dimensionId": "constructive-alignment",
  "coverage": { "criteria": 2, "denominator": 2, "pass": 0, "fail": 2,
                "noEvidence": 0, "notApplicable": 0, "notAssessed": 0, "executionError": 0 }
}
```

Two criteria, both failed, so 0/2. To see *why* they failed — the passage the judge read and
the failure mode it named — open `/admin/studies/<id>` in the console and expand the
criterion.

Each course also carries its `briefId`, which is how you group results by commission. **The
system deliberately does not average per commission**: if you generate more than one course
from the same commission, it hands you each one labelled, because averaging them would erase
exactly the spread that repeating a commission exists to reveal. The mean and the dispersion
are yours to compute.

## The one rule that will bite you

**Only compare values computed over the same coverage, with the same formula version, the
same instrument version and the same judge.**

A run where four criteria ended in `execution_error` has a smaller denominator than one where
none did. Both values are correct; their *difference* is not. The same holds if you change the
instrument or the assessor midway: the population changes underneath, and every number from
before stops being comparable with every number after.

In practice: **decide the instrument version and the assessor before the first batch, and do
not change either until the work is done.** Both travel in the document
(`instrumentVersionId`, `assessorCoverage.assessorsUsed`) so a stored result can always be
checked, and `assessorCoverage` carries the `notAssessed` and `executionErrors` counts that
say whether two results may be subtracted.

## Turning it into one number

If you need a scalar, you define it. The minimum it has to handle:

- **Which dimensions count, and how much.** An unweighted mean of the five is a defensible
  default; weights are a claim about what you are optimizing for, so write down whichever you
  choose.
- **`undefined`.** Skip it. A dimension answers `undefined` when none of its qualities was
  measured; reading that as `0` scores the generator on a question nobody asked, and it is the
  mistake that quietly wrecks a comparison.
- **How many courses.** A round over two courses and a round over twenty are both valid and
  are not equally trustworthy.

Keep the raw document, not just your scalar. The scalar is a summary you may want to redefine
later; the document is the measurement.

## What a batch costs

An assessor that carries an LLM spends real calls on your key. `drafts-hybrid` runs at
roughly **30 calls per course** — `/admin/assessors` shows exactly which criteria it executes
and which it abstains from, and the abstained ones are why a batch is cheaper than 29 criteria
would suggest.

| Batch | Calls | Rough wall time at concurrency 4 |
|---|---|---|
| 4 courses | ~120 | a few minutes |
| 12 courses | ~360 | 15–30 minutes |
| 24 courses | ~720 | 30–60 minutes |

`drafts-structural` is the other judge for the same instrument: it is pure code, spends
nothing, and covers only the structural criteria. It is a good way to check that a folder
registers and reads correctly before paying for a real batch.

## When something does not work

| What you see | What it is |
|---|---|
| `no source root named 'generated'` | not declared in `.env`, or the API started before you declared it — restart it |
| `the dev mount does not serve this course` | the API is not running |
| `INVALID … could not read artifact` | that package is missing a file the format requires; the other courses still register |
| `N assessors have ratified …` | pass `--assessor` |
| `N published instrument versions bind …` | pass `--instrument-version-id` |
| `folder 'unknown' declares no generator version` | a round measures named versions; name the version in the folder |
| `already registered under a different generator version` | those courses were first registered under another version and keep it. Measure the version that holds them, or start clean with `task db:reset` |
| `is behind` / `alembic upgrade head` | the database is older than the code |

Two more worth knowing before they surprise you:

- **A course's identity is its content.** Registering the same bytes twice returns the course
  that already exists, keeping the generator version it was first registered with. If two
  versions produce a byte-identical course, the second round will not include it — and will
  say so, per course.
- **The judge is not perfectly consistent.** Repeated runs over identical input mostly agree,
  but not always, so a small difference between two batches may be the judge rather than the
  generator. That is one more reason to keep the per-course values and not only the mean. What
  repeated runs have shown, and how to tell a wobbling judge from a criterion with no threshold
  written down, is in `../backend/README.md` under *What repeated runs tell you*.

## Where to look next

- `/admin/studies/<id>` — the round: the weakest claims, the most-failed criteria, and the
  passage the judge quoted for each.
- `/admin/measure` — the same loop as the command, in the console.
- `/admin/calibration` — run one course against one instrument without persisting anything,
  and read every LLM call it made.
- `backend/README.md` — everything else, including how instruments and assessors are built.
