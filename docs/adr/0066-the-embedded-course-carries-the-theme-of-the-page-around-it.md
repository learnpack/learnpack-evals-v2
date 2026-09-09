# ADR-0066 — The embedded course carries the theme of the page around it

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Evaluation Orchestration
(evaluator surface) · Course Session

## Context

The console now offers light, dark and the device's own, and the evaluation screen is half
course: an iframe pinned beside the scoring form, given a session so its AI answers (ADR-0061).
A dark console with a white course inside it is not a small blemish. It is the largest thing on
the screen disagreeing with everything around it, on the one screen a subject-matter expert
spends an hour in.

Nobody inside the frame can fix it either. Being embedded already hides the course's own theme
switch — that is what `iframe=true` is for, and dropping controls that belong to nobody on this
screen was the point of asking for it. So either the host decides, or nothing does.

What the course platform offers is one lever and it is exact:

- A `theme` query parameter, validated against its own two words (`light`, `dark`) and silently
  ignored otherwise. It is read **once**, while the player boots, and the value becomes a class
  on the element the whole page's variables hang off.
- **No inbound message channel.** The player registers no listener for its parent; the only
  protocol that exists runs the other way, one message, when a lesson is finished. A host
  cannot ask a loaded course to change anything.
- **No `prefers-color-scheme`.** With no parameter the course is always light, whatever the
  device says.

## Decision

**The frame is served in the theme the console is in, spelled into the URL at load — and a
change of theme reloads the course.**

### 1. The theme is composed where being embedded is known

Beside `iframe=true`, in the component that mounts the frame, for the reason already written
there: the URL the backend mints is also what "open in new tab" opens, and a course opened in
its own tab is **not** embedded. Being embedded is known only by whoever embeds.

### 2. The link out keeps its plain URL

A course in its own tab is the course's, and it has its own switch there. Holding it to this
page's theme would be the same mistake as hiding its language selector outside the embed.

### 3. `system` is resolved before it reaches the URL

The platform accepts two words. `system` is not a third theme; it is a question about a device,
which the browser has already answered by the time the frame renders. The frame is given the
answer.

### 4. The frame waits for the theme, as it already waits for the session

The chosen theme lives in the browser, so the first server-rendered pass does not know it.
Rendering the frame on a guess would load the course once in the wrong theme and again in the
right one — the double load the session already exists to avoid.

### 5. The reload is accepted, and it is the whole cost

Changing the theme with a course open loads it again. There is no way around it that does not
run through somebody else's release: the parameter is read at boot and nothing listens
afterwards. The evaluator does not lose their place, so what it costs is a few seconds.

### 6. What will not follow the theme, and is not ours to fix

Inside the course, code blocks and the embedded editor are pinned dark whatever the theme, and
the course's dark ground is its own navy rather than ours. The frame already declares that what
is inside belongs to somebody else — a bar naming it, a border, a ground of its own — so a
course that is *its own* shade of dark is legible as a course, not as a broken panel.

## Consequences

- **One screen stops disagreeing with itself.** In dark, the largest surface an evaluator reads
  is dark.
- **The theme is one more thing the frame is given**, alongside the session, and it fails the
  same way: an unknown value is ignored by the platform and the course renders light, which is
  what it did before this decision existed.
- **A change of theme mid-review costs a reload of the course.** Whoever wants that gone has to
  land a listener in the player; the change is small and would reach every deployed course at
  once, because they all load the same published bundle.
- **The screenshot in a bug report now depends on a preference.** Anyone reproducing what an
  evaluator saw needs to know which theme they were in.

## Alternatives considered

- **Leave the course light always.** The cheapest, and it is the defect: the console cannot
  offer a dark screen and then hand over most of that screen in white.
- **Add an inbound `postMessage` to the player and drive it live.** The right fix, and it is
  not ours to schedule: it lands in another product's release. Nothing here forecloses it — the
  day a loaded course can be told, this is one function.
- **Drop `iframe=true` so the course keeps its own switch.** It would bring back the language
  selector and a theme control that answers for a region of our page, and it would leave the
  evaluator two switches that disagree.
- **Let the evaluator choose the frame's theme separately.** A second control for a preference
  they already expressed, on the screen with the least room for one.

## References

ADR-0061 (the frame is given a minted session; the same URL is what "open in new tab" opens) ·
ADR-0028 (`consumable_url` — a deployed instance is declared, and it is what the frame points
at) · `frontend/src/components/evaluator/consume-content.tsx` (the frame, its chrome and the
two silences it turns into sentences) · `frontend/README.md` §Theme (how the console's theme
works, and what is told separately because it does not paint with our tokens).
