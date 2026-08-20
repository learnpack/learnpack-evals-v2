# design — snapshots of the modelling process

**Everything in here is frozen.** These are the artifacts of the DDD Starter Modelling Process
(ddd-crew) and their inputs: they record **what we thought and why, at the moment we thought it**.

Contract of this folder:

- **Not maintained.** If the system changes and contradicts one of these documents, the document
  is **not corrected**: the code and the current docs win (`../ARCHITECTURE.md`, `../GLOSSARY.md`,
  the READMEs of `backend/` and `frontend/`). If the contradiction matters, an ADR is written.
- **They do not describe the current state.** That is what `../../STATUS.md` is for.
- They are read to understand **the why** of a boundary or a name, not to know how the system
  is today.
- **Supersession:** a closing of the process leaves its snapshot; the next round supersedes it with
  new docs and a banner on the old ones (same model as the ADRs).

## Current series — second round (Aug-2026): internal QA of generators

| Doc | Steps | Content |
|---|---|---|
| `09-align-discover-qa.md` | Align + Discover | internal QA purpose, genesis triad, ECD-lite, the two loops, user journey, human reference in two layers |
| `10-decompose-strategize-qa.md` | Decompose + Strategize | 9 subdomains, events, flow, study lines, core chart, investment guide |
| `11-connect-qa.md` | Connect | context map, integration rules, composed queries (matching/readiness), ACLs, published language |
| `12-define-qa.md` | Define | canvases of the 5 contexts + the 4 by reference (self-contained), invariants, deferrals, first-increment marks |

Decisions with alternatives: `../adr/0009` … `0015`. Inputs: `research/qa-evals-landscape.md`.

## Historical series — first round (Jul-2026): design of slice 1 (human MVP)

**Do not use as a source for new code** (banner on each doc).

| Doc | Step | State when frozen |
|---|---|---|
| `01-align.md` | Align | closed — superseded by 09 |
| `02-discover.md` | Discover | closed — superseded by 09 |
| `03-decompose.md` | Decompose | closed — superseded by 10 |
| `04-strategize.md` | Strategize | closed — superseded by 10 |
| `05-connect.md` | Connect | closed — superseded by 11 |
| `06-organise.md` | Organise | placeholder (still true in spirit) |
| `07-define.md` | Define | closed — superseded by 12 (self-contained) |
| `08-code.md` | Code (MVP plan) | closed — implemented; the slice 2 plan will be its own doc |
| `research/` | Dated external inputs and field runs | `deterministic-evaluation-landscape.md` (Jul) · `qa-evals-landscape.md` (Aug) · `concept-continuity-field-runs.md` (Aug — the evidence behind ADR-0047) |
