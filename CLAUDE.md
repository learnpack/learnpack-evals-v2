# CLAUDE.md

Guide for generating the code of this repository. **Read `docs/` before writing code.**

## Reading order
1. `docs/ARCHITECTURE.md` — non-negotiable invariants (start here).
2. `docs/GLOSSARY.md` — ubiquitous language (code names come from here; it includes the
   **equivalences table with the evals industry**).
3. `docs/design/09-align-discover-qa.md` … `13-code-qa.md` — **the current design** (internal
   QA of generators): strategic (09–11), tactical per context (12) and the code
   plan (13), the latter as it was written **before** implementing.
4. `docs/adr/` — immutable decisions: 0001–0008 (slice 1) · **0009 onwards (slice 2)**.
5. `STATUS.md` — where the development stands **today**.

⚠️ `docs/design/01-…-08` are **historical snapshots** of the design that produced slice 1 —
they carry a banner and are **not used as a source for new code**.

⚠️ The 09–13 series is **not** historical — it is the model the code realizes — but it is
frozen at what was written before implementing, and several later ADRs amend it. **Never read
one of those snapshots alone**: where a snapshot and an ADR disagree, the ADR wins, and each
ADR names what it amends in its own references.

## Non-negotiables (summary of ARCHITECTURE.md)
- **Dependency Rule:** dependencies point **inwards only**
  (Frameworks → Adapters → Application → Domain). The **Domain is pure Python**: no FastAPI,
  SQLAlchemy, LiteLLM or I/O.
- **Ports & adapters:** ports are defined in Application/Domain; adapters (Postgres/Neon,
  Clerk, LiteLLM) are implemented outside and injected.
- **Module isolation:** modules talk via **domain events + query DTOs**; another module's
  internal domain is never imported. ACL at the external boundaries (LearnPack, LLM).
- **Events-first:** state evolves via domain events; policies react; no cross-module
  commands. In the MVP an event is an `INSERT` into the `events` table (outbox, ADR-0003).

## Documentation — where to write what (hard rule)

Every document has a **maintenance contract**, and its location declares it. Before writing
a `.md`, choose its class:

| Class | Where | Contract |
|---|---|---|
| **reference** | root of `docs/`, `backend/README.md`, `frontend/README.md` | **Always true of `main`.** Updated in the **same commit** as the code that makes it false. |
| **decision** | `docs/adr/` | **Immutable.** The content of an ADR is never edited: a new one is written that supersedes it. Sole exception: the **Status** line of the superseded ADR is updated to "superseded by ADR-XXXX" — lifecycle metadata, so nobody acts on a dead decision. |
| **snapshot** | `docs/design/` | **Frozen.** Not maintained or corrected, even if the system contradicts it. |
| **working** | `notes/` (gitignored) | Ephemeral. When the task closes it is **promoted or deleted**. |

Non-negotiable rules:

1. **No status outside `STATUS.md`.** No "already done", no "X missing", no "N tests
   green", no "✔ verified on 30-Jul", no dates of when something was tested. A reference doc
   states **how it works and why**, in the present tense and undated. Status goes to
   `STATUS.md`, which is rewritten whole.
2. **Every analysis, plan or investigation is born in `notes/`** — not in `docs/`. Including
   what you generate (implementation plans, audits, comparisons).
3. **When the task ends, each note has four exits and only four:** it was a *decision with
   discarded alternatives* → ADR · it was a *rule or instruction* → merged into an existing
   reference (not a new file) · it was a *point-in-time analysis* → frozen in
   `docs/design/` · **none of the above → it is deleted**.
4. **Test for admitting something into reference:** will it still be true six months from now
   without anyone touching it? If not, it does not go there.
5. **Operational content lives next to the code it operates** (`backend/`/`frontend/`
   READMEs); `docs/` is only for the cross-cutting.
6. **Before creating a new `.md`, look for where to merge it.** A new doc is justified by
   having a lifecycle of its own, not by being a new topic.

## Conventions
- **Ubiquitous language, code and ALL documentation in English** — docs and business comments
  included. Use exactly the names from `docs/GLOSSARY.md`.
- Always distinguish: `EvaluationSource` (type/port) vs. `Assessor` (versioned instance) ·
  `Criterion` (what is verified) vs. `Assessor` (who/how produces it) · `ComputedMetric`
  (measurement) vs. `CriterionScore` (discrete outcome + quote) · immutable `instrumentVersion`
  + **pinning** per study.
- **The terms of the evals industry** (experiment, scorer, run, dataset…) do not name domain
  concepts: they appear only in adapters (ACL) and in the equivalences table of the
  `GLOSSARY.md`.

## Two horizons (critical)
- The **current model** (internal QA of generators) is complete in `docs/design/09–12` and its
  code plan in `13-code-qa.md`, but **the first increment is a thin slice** — see the
  "first increment: thin/no" marks in `12-define-qa.md` and the **explicit deferrals to
  Code**, already decided in `13-code-qa.md` §7 (sufficiency, validity metrics, annotation
  queues, value domains).
- Explicit `[future]` items: assessor calibration, generator-grain claims with their own rule,
  deliberation, outgoing integration events. Do not build them without a decision.
- When in doubt: implement the minimal slice **without closing doors** on the 09–12 model; if a
  new decision contradicts the design, an ADR is written first.

## Stack
**MVP (confirmed):** Next/Tailwind + an in-house shadcn-style kit on Netlify · FastAPI on
Render Starter · Postgres on Neon · Clerk (invite-only). See `docs/design/08-code.md`,
ADR-0003 and ADR-0004.
**Target `[future]`:** LiteLLM/OpenRouter and LangGraph (only if orchestrating agents becomes
necessary) — not used in the MVP.
