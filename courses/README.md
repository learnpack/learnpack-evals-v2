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

The folder name declares the generator (ADR-0024): `<name>@<version>` must match a
**registered** GeneratorVersion — the import refuses unregistered ones and never creates
generator identities. The special folder `unknown` registers its courses with no generator.

## Usage

The dev API must be running (`AUTH_MODE=local`): it serves this tree at `/packages`, so the
registered locators and `consumable_url` are honest http URLs.

```bash
# one course
python -m app.cli register-package --source courses/unknown/my-course --generator unknown

# everything under courses/
python -m app.cli register-package --all
```

Re-importing an unchanged course is a no-op (content hash); a changed course under the same
declared version is refused — pass `--version` to register it as a new version.
