# Local courses (dev intake — ADR-0027)

Drop downloaded LearnpackV1 course packages here to register and evaluate them locally.
Everything in this directory except this README is **gitignored**: course content is data,
never part of the repo.

## Layout

```
courses/
  <generator-name>@<generator-version>/   # one folder per registered GeneratorVersion
    <course-slug>/                        # the downloaded package, as-is
      learn.json
      .learn/…
      exercises/…
  unknown/                                # courses whose generator is declared unknown
    <course-slug>/
```

The folder name declares the generator (ADR-0024): `<name>` must match a **registered**
`Generator` and `<version>` one of its registered versions (ADR-0031). The import refuses
unregistered ones — naming which half is missing — and never creates generator identities. The
special folder `unknown` registers its courses with no generator.

## Usage

Prerequisites (from `backend/`): local DB up, `.env` with `AUTH_MODE=local`, and the
dev API running — it serves this tree at `/packages`, so registered **locators** are
fetchable http URLs (that is what brief intake and profiling need). Because they are http,
registering a course here also **auto-profiles** it once the extraction is accepted
(`accept-extraction`, ADR-0012); the command prints what the policy did.

Dropping a course here does not deploy it, so a course registered from this tree declares
**no consumable URL** (ADR-0028): it can be evaluated automatically, and the admin console
marks it *not deployed* and refuses to assign it for human scoring. If the course is in fact
deployed somewhere, declare it with `--consumable-url <https://…>`.

```bash
cd backend

# one course (path relative to backend/; parent folder must be unknown or <name>@<version>)
uv run python -m app.cli register-package \
  --source ../courses/unknown/my-course \
  --generator unknown

# everything under courses/<name>@<version>/ and courses/unknown/
uv run python -m app.cli register-package --all
```

Re-importing an unchanged course is a no-op (content hash); a changed course under the same
declared version is refused — pass `--version` to register it as a new version.
