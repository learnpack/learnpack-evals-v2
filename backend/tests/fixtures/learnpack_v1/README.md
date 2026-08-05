# LearnpackV1 frozen packages

The test investment of Content Profiling (design 10): the `LearnpackV1` extraction adapter
is specified by these packages, not by mocks. Never edit the real ones — a format change in
LearnPack means freezing a new package and, if extraction must change, a new
`ADAPTER_VERSION`.

- `introduction-to-generative-ai/`, `object-representation-in-python/` — real generated
  LearnPack courses (the same two the demo seed registers), trimmed to what the adapter
  reads: `learn.json`, `.learn/package-manifest.json` (the `lessons[]` index) and, per
  lesson under `exercises/<slug>/`, the English `README.md` plus code-exercise files and
  their `<stem>.solution.hide.<ext>` reference solutions. Translations, assets and
  previews are not part of the extraction surface. Notable real quirks the tests rely on:
  the intro course has lessons with ids `05` and `06` (numbering drift the instrument's
  well-formedness criterion exists to catch), and both courses embed multiple-choice
  (task-list `[x]`) and open-question (```question) activities.
- `bare-course/` — hand-made minimal package: a frontmatter-only lesson (no activities),
  a lesson with no README but a code exercise missing its solution, and an
  activity-sampler lesson with one of each embedded component (including the legacy
  `fill_in_the_blank` fence) plus decoys that must not count (a checkbox inside a foreign
  fence, an author-facing `code_challenge_proposal` block).
- `broken-course/` — `.learn/package-manifest.json` is deliberately not valid JSON;
  extraction must fail into a `failed` profile, never crash.

Tests read them through `FilesystemPackageFetcher` with this directory as base; locators
are the relative paths inside each package.
