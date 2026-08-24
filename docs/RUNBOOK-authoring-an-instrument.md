# Authoring an instrument

This is the guide for one job: deciding what a study should assert about a generator's
output, and writing it down as something the system can execute. It assumes you have the
repository running — [`../backend/README.md`](../backend/README.md) is the setup — and it
does not assume you have read the design.

The other side of the same coin is [adding a package format](RUNBOOK-adding-a-format.md): a
format teaches the system to *read* something, an instrument decides what is worth *asking*.

Every command below is run from `backend/`, which is why the paths inside them start at
`../docs/`. Paths in prose are relative to this file.

An *instrument* is the **evidential argument** a study pins: what is being asserted about a
generator's output, and what would count as evidence for it.

Authoring is file-based and assistant-drafted, publishing is a human act, and a published
version never changes. This table decides which command you want; the rest of the runbook is
about what to write.

| You want to… | Then… |
|---|---|
| Create an instrument, or keep editing one that is still a **draft** | Edit the YAML and `import-instrument --file <yaml>` — the draft is replaced in place, as often as needed (no bump involved). Import also mints the `data_requirement` ids the extraction conforms to (ADR-0014). |
| Lock a draft so evaluations and studies can rely on it | `publish-instrument --id <version-id> --email <admin>`, or the Publish button in `/admin/instruments`. Publish validates the full evidential argument; from here the version is immutable. |
| Change anything in a **published** version — a threshold, a wording, a new criterion | `bump-instrument --file <yaml> [--to vN] [--reason "…"]` clones the YAML into the next version's file **textually** (header comments and block-scalar style survive; only `version:` and, with `--reason`, `revision_reason:` change), then: edit the new file → `import-instrument` → `publish-instrument`. Claim/criterion ids stay stable across versions — the lineage. |
| Change the declaration of an **existing** `data_requirement` — reword the definition (same meaning) or adjust its `value_domain` | Edit it in the YAML and add `--revise-definitions` to `import-instrument`: the deliberate act that lifts the ADR-0014/0020 lint; each revision is applied and reported old → new. Without the flag the lint blocks — the guardrail against silently rewriting the contract adapters conform to. |
| Express a **different** concept than an existing `data_requirement` | Do NOT revise it — mint a new id with its own definition (ADR-0014: same meaning → alias or revision; similar-but-different → new id). |

`bump-instrument` refuses collisions (target file on disk, target version in the db) and
self-checks the textual edit before writing, so it never produces a corrupt or overwritten
file.

**The chain, in one line.** A **quality** is what we care about · a **claim** asserts one
thing about **exactly one** quality (ADR-0026) · a **criterion** is a check whose outcome
evidences a claim · a **data requirement** is a datum a criterion needs to be executable, and
an extraction adapter is what supplies it. You author from the top down and the system
validates from the bottom up.

There is no aggregate score across criteria and there never will be (ADR-0011). An instrument
reports per criterion, per claim; anyone looking for one number is looking for a different
system.

## Step 0 — Do you actually need a new instrument?

Usually not. **An instrument forks when its claims change, not when the package format
changes** (ADR-0032). A new format normally joins the instrument you already have: add a
`bindings` entry, publish the new version, done.

Criteria the new format's extraction cannot feed derive `not_applicable`. That is a report,
not a defect — demand stated honestly and left unanswered — and it is not a reason to fork.

Measure it before deciding:

```bash
GET /admin/instruments/{instrument_version_id}/matching?package_format=<name>
```

It returns, per criterion, what it requires and what is missing; the unmet demand grouped by
data requirement; and per claim, how many of its criteria are covered. **A claim with zero
covered criteria is the signal to read closely**: either the format cannot answer a question
that still applies, or the question does not apply to that artifact at all. The second case is
where a second instrument is warranted — and what justifies it is the different question, not
the different format.

## Step 1 — Know what you cannot mint here

Qualities, dimensions and frameworks are **reference data**, not instrument content. They live
in `seed/pedagogical-reference.yaml` and enter with `uv run python -m app.cli seed`.
Your instrument *references* their ids; publishing refuses ids that do not exist.

So if your argument needs a quality nobody has named yet, that is an edit to the reference
file and a reseed — before you publish, not during. The same goes for a warrant: a claim can
only cite a framework the reference declares.

## Step 2 — Reuse data requirement ids; mint only what is new

The demand-side namespace is **global across instruments** (ADR-0014). A criterion may require
an id that already exists without redeclaring it in your file — inheriting `lesson_bodies` or
`course_descriptor` costs nothing and keeps one meaning per id.

Declare a `data_requirements` entry only for an id you are **minting**, and write its
`definition` and its `value_domain` at that moment: the definition says what the datum means,
the value domain says what shape it takes, and both are the contract extraction adapters
conform to (ADR-0020).

Redeclaring an existing id with a different definition or a different shape is blocked by a
lint. That is the guardrail, not an obstacle — decide which case you are in:

| Situation | What to do |
|---|---|
| Same meaning, different words | Keep the existing definition, or add an `aliases` entry |
| Same meaning, the declaration itself is wrong | `import-instrument --revise-definitions`, the deliberate act |
| Similar but **not** the same thing | Mint a new id with its own definition |

One constraint that bites from the other side: **an extraction adapter cannot declare a
capability for an id no instrument declares.** The format contract kit asserts
`capabilities ⊆ declared_value_domains()`. So a datum and its supply land together — mint the
id in the instrument and teach the adapter to produce it in the same change, or the kit
refuses one half of it.

## Step 3 — Write the YAML

One file per version, `seed/instruments/{instrument_id}-{version}.yaml`.
`learnpack-course-qa-v1.yaml` is the worked example to read alongside this.

| Key | What it carries |
|---|---|
| `instrument_id`, `version`, `name`, `purpose` | The identity and what the argument is for |
| `assisted_by` | What drafted it and in what role — assistance is recorded, never hidden |
| `bindings` | The `package_format`s this version is designed for, plus `task_variables` a criterion conditions on (demand-driven: add one when a criterion needs it, not before) |
| `data_requirements` | Only the ids you mint (step 2) |
| `claims` | `statement`, one `qualities` entry, `warrants`, `sufficiency`, `alternative_explanations` |
| `criteria` | `statement`, `pass_condition`, `failure_modes`, `claims`, `requires`, `on_missing_evidence`, `eligible_sources` |

Four things that are easy to write carelessly:

- **`alternative_explanations`** on a claim is the discipline that keeps a `fail` honest: what
  else could produce this evidence besides the defect you are asserting? Write the ones a
  dispute would raise.
- **`on_missing_evidence`** decides what a criterion does when its datum is absent. `fail`
  says the absence **is** the finding (ADR-0021 records it as derived, with no quote);
  `no_evidence` says absence settles nothing. Choosing `fail` is a claim in itself — make it
  deliberately.
- **`pass_condition` and `failure_modes` are read by more than people.** An assessor that
  judges with an LLM puts them **verbatim into the model's prompt**, so they have to stand on
  their own: no criterion ids, no file names, no "that is handled elsewhere". A model has no
  referent for those and, told about a neighbouring concern, will reason about the thing it
  was asked not to judge. State an exclusion in its own terms — *"naming what comes next is
  not teaching it"* — and stop there; the cross-reference belongs in a YAML comment, which
  never reaches the model.
- **The criteria of one claim must not contradict each other.** `sufficiency: conjunctive`
  means every criterion has to pass, so if one passage can fail one criterion for being
  present and another for being absent, that claim is **unsatisfiable** for that shape of
  content — and no evidence will ever fix it. Read a claim's criteria together, against a
  real example, before publishing. This is not hypothetical: `cl-course-closes-by-integrating`
  shipped with exactly that defect and it took an LLM oscillating between the two readings to
  make it visible.

`sufficiency` today has one built rule: `conjunctive`. `existential` and `m_of_n` are
documented vocabulary, not behavior — do not author against them yet.

## Step 4 — Import, then make publish green

```bash
uv run python -m app.cli import-instrument --file ../docs/seed/instruments/<file>.yaml
uv run python -m app.cli publish-instrument --id <version-id> --email <admin>
```

`import-instrument` creates or replaces a **draft** and runs the lint: data requirements
well-formed, no divergent redeclarations, no criterion requiring an id nothing defines. It
reports every problem in one run rather than stopping at the first.

`publish-instrument` validates the **whole evidential argument**, and that list is this
runbook's equivalent of the format contract kit — the executable definition of a complete
instrument:

- every criterion references a claim that exists;
- every criterion's required data is inside the namespace;
- there is at least one claim;
- every claim has at least one criterion evidencing it;
- every claim asserts about **exactly one** quality (ADR-0026);
- every quality and every warrant a claim cites is known reference data;
- there is at least one `bindings` entry.

Iterate on the draft as often as you like — it is replaced in place, no version bump involved.
Publishing is the point of no return: from there the version is immutable and any change is a
new version (`bump-instrument`).

## Step 5 — The recorded human acts

1. **Publish** — the act above. Nothing assistant-drafted reaches published without a human
   performing it.
2. **Ratify the assessors** against this instrument version (ADR-0019), from the CLI or from
   `/admin/assessors` (ADR-0036 — the page shows the text of each criterion whose decision
   the act is waiting for). Within one lineage
   this is cheap — the diff against the previous version is computed mechanically and only
   changed or new executed criteria need `--confirm`. Across instruments it is not a diff at
   all: an assessor vouched for one argument has not been vouched for another, so a new
   instrument ratifies from scratch. Criteria no assessor can execute derive `not_assessed` —
   the visible backlog, not a failure. There is no un-ratify: if the decision was wrong, the
   exits are a new assessor version or a new instrument version.

   One prerequisite the act cannot supply: a **new lineage** can ratify nothing until an
   assessor artifact declares itself against it — coverage is code, not an act. The
   declaration is the package's `INSTRUMENT_ID`
   (`backend/app/modules/evaluation/infrastructure/assessors/<name>/__init__.py`), and
   `ratify-assessor` refuses a package whose `INSTRUMENT_ID` names another lineage. Writing
   that package is the prerequisite; ratifying it is the human act.

3. **Record which version a local workbench uses** — once the new version is the one to
   measure with, replace the lineage's line in `seed/workbench.yaml`. That is what a
   rebuilt database publishes and what every assessor of the lineage is then ratified against
   (ADR-0045); the manifest holds one version per lineage on purpose.

## Step 6 — Verify end to end

Calibrate while it is still a draft — `evaluate --content-id <id> --instrument-version-id <id>
--assessor <name>:<version> --dry-run` persists nothing and prints the outcome table, so you
can read what your criteria actually do against real content before freezing them. It is also
the **only** way to exercise an instrument whose lineage has no assessor yet: the dry run does
not compare lineages, so any registered package's executors can be pointed at any version.
Then the study path:
`declare-study [| update-study] | open-study` →
`evaluate-study` → `show-preview` → `sign-off-study` → `show-report`. The study needs a
**generator scope** before it can open (`--all-generator-versions`, or
`--generator-version-id` once per version it measures — several of them is an A/B between
them, ADR-0044).

## What you never touch

A published version, ever — bump instead · the qualities and frameworks from inside an
instrument file — they are reference data (step 1) · the meaning of an existing data
requirement id without `--revise-definitions` · the domain rules publish enforces. If your
argument seems to need one of these bent, it needs an ADR first.

## Where to look next

- [Adding a package format](RUNBOOK-adding-a-format.md) — teaching the system to read a new
  packaging convention.
- [Calibrating an instrument](RUNBOOK-calibrating.md) — finding out what a criterion should
  ask, before you write it.
- `MEASUREMENT.md` — where every threshold a criterion leans on comes from.
- `../backend/README.md` — setup, the commands around these, and the code's shape.
