# LearnpackV1 frozen packages

The test investment of Content Profiling (design 10): the `LearnpackV1` extraction adapter
is specified by these packages, not by mocks. Never edit the real ones — a format change in
LearnPack means freezing a new package and, if extraction must change, a new
`ADAPTER_VERSION`.

Five of them are real generated LearnPack courses, trimmed to what the adapter reads:
`learn.json`, `.learn/package-manifest.json` (the `lessons[]` index),
`.learn/initialSyllabus.json` (the commission, ADR-0022) and, per lesson under
`exercises/<slug>/`, the English `README.md` plus code-exercise files and their internal
`<stem>.solution.hide.<ext>` companions (frozen to prove the adapter excludes them from
the exercise list). Translations, assets and previews are not part of the extraction
surface.

Together they are also the **calibration corpus**: the empirical thresholds of the
quantitative criteria are set against these five and no others, and a test pins the
verdict each one produces. See `docs/MEASUREMENT.md` for what is measured and why —
changing this set changes what those numbers mean.

- `introduction-to-generative-ai/`, `object-representation-in-python/` — the two the demo
  seed registers. The intro course has lessons with ids `05` and `06` (numbering drift the
  well-formedness criterion exists to catch); the Python one declares two `CODE` lessons
  (`01.3`, `02.3`) that ship **no exercise file at all** — a declared practice never
  delivered. Both embed multiple-choice (task-list `[x]`) and open-question (```question)
  activities.
- `ai-concepts-an-exploration-inside-ai/` — no exercise files anywhere and only 2 of 9 core
  lessons carry any activity, so it is the corpus's floor for `cr-lessons-with-activities`.
  It also holds the sharpest lexical-load spike (`05.1`) and its shortest lesson is short
  but complete — the false positive that killed a length-balance criterion.
- `html-fundamentals/` — the counter-example to naming assumptions: its exercise files are
  `index.html`, `app.html` and `about_me.html`, never `app.py`, so an adapter that keyed on
  a filename would find nothing here. It is also the inverse of the Python course's defect:
  **7 lessons ship exercise files while the manifest declares none of them `CODE`**. The
  declared `type` is unreliable in both directions, which is why the criterion that reads it
  derives `not_applicable` rather than `pass` when no `CODE` lesson is declared.
- `orchestrating-a-multi-agent-system-in-langgraph/` — the well-behaved case for the same
  check: two `CODE` lessons, both delivering their exercise. Its lexical load sits closest
  to the threshold of any package, which is what makes it worth keeping.
- `bare-course/` — hand-made minimal package: a frontmatter-only lesson (no activities),
  a lesson with no README but a code-exercise file, and an activity-sampler lesson with
  one of each embedded component (including the legacy `fill_in_the_blank` fence) plus
  decoys that must not count (a checkbox inside a foreign fence, an author-facing
  `code_challenge_proposal` block).
- `broken-course/` — `.learn/package-manifest.json` is deliberately not valid JSON;
  extraction must fail into a `failed` profile, never crash.

Tests read them through `FilesystemPackageFetcher` with this directory as base; locators
are the relative paths inside each package.
