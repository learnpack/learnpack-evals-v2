# LearnpackV1 frozen packages

The test investment of Content Profiling (design 10): the `LearnpackV1` extraction adapter
is specified by these packages, not by mocks. Never edit the real ones — a format change in
LearnPack means freezing a new package and, if extraction must change, a new
`ADAPTER_VERSION`.

- `introduction-to-generative-ai/`, `object-representation-in-python/` — real generated
  LearnPack courses (the same two the demo seed registers), trimmed to what the adapter
  reads: `learn.json`, `.learn/config.json` and the English `exercises/*/README.md`.
  Translations, assets, previews and solution files are not part of the extraction surface.
- `bare-course/` — hand-made minimal package for the poor paths: one exercise whose README
  is frontmatter-only (no learner-facing instructions) and one with no README at all.
- `broken-course/` — `.learn/config.json` is deliberately not valid JSON; extraction must
  fail into a `failed` profile, never crash.

Tests read them through `FilesystemPackageFetcher` with this directory as base; locators
are the relative paths inside each package.
