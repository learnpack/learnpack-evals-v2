"""LearnpackV1 extraction adapter — deterministic, no LLM, no inference (ADR-0009).

What a LearnPack package actually offers (frozen in `tests/fixtures/learnpack_v1/`):
`learn.json` declares slug/title/technologies/difficulty/description — NO objectives,
audience or prerequisites as structured fields — and `.learn/config.json` carries the
authoritative `exercises[]` index; learner-facing instructions live in each exercise's
`README.md` (YAML frontmatter + body). Therefore:

- `learning_objectives` / `target_audience` / `prerequisites` come from the content's
  DECLARED metadata (`declared_structured`) or are `absent` — they exist nowhere in the
  package itself, and reconstructing them from description prose would be inference.
- `practice_exercises` comes from the `exercise_config` artifact; whether an exercise has
  instructions is observed in its `exercise_instructions` artifact (README body non-empty
  after stripping frontmatter).

Artifact kinds the adapter understands (open vocabulary, this adapter's convention):
`manifest` (learn.json) · `exercise_config` (.learn/config.json) · `exercise_instructions`
(exercises/<slug>/README.md — the slug is the locator's parent directory, as in the real
layout). Any artifact it chooses to read that cannot be fetched or parsed raises
`ExtractionError` → a `failed` profile, never a crash and never a half-profile.

Any change in this mapping is a new ADAPTER_VERSION: the version is the identity of the
extraction, and each one requires its own `ExtractionAccepted` act.
"""

import json
from typing import Any

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.content_profiling.application.ports import PackageFetcherPort
from app.modules.content_profiling.domain.profile import (
    ExtractionError,
    ProfileEntry,
    ProfileExtra,
)

PACKAGE_FORMAT = "LearnpackV1"
ADAPTER_VERSION = "1"

CAPABILITIES = frozenset(
    {"learning_objectives", "target_audience", "prerequisites", "practice_exercises"}
)

# Registry metadata key (camelCase, the seeded MetadataSchema) → data requirement id.
_METADATA_CAPABILITIES = {
    "learningObjectives": "learning_objectives",
    "targetAudience": "target_audience",
    "prerequisites": "prerequisites",
}

KIND_MANIFEST = "manifest"
KIND_EXERCISE_CONFIG = "exercise_config"
KIND_EXERCISE_INSTRUCTIONS = "exercise_instructions"


def _quote(value: Any) -> str:
    """The verbatim citation of a declared value, serialized canonically (deterministic)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json(raw: bytes, locator: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"artifact '{locator}' is not valid JSON: {exc}") from exc


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block; what remains is the learner-facing body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    return text


def _exercise_slug(locator: str) -> str:
    """The exercise a README belongs to — its parent directory in the package layout."""
    parts = locator.replace("\\", "/").rstrip("/").split("/")
    return parts[-2] if len(parts) >= 2 else ""


class LearnpackV1Adapter:
    @property
    def package_format(self) -> str:
        return PACKAGE_FORMAT

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    @property
    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES

    def extract(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> tuple[tuple[ProfileEntry, ...], tuple[ProfileExtra, ...]]:
        entries = [
            *self._from_declared_metadata(package),
            self._practice_exercises(package, fetcher),
        ]
        return tuple(entries), self._extras(package, fetcher)

    # --- declared metadata (the registry's, ADR-0001) -----------------------------------

    def _from_declared_metadata(self, package: PackageDTO) -> list[ProfileEntry]:
        entries = []
        for key, requirement_id in _METADATA_CAPABILITIES.items():
            if key in package.declared_metadata:
                value = package.declared_metadata[key]
                entries.append(
                    ProfileEntry(
                        data_requirement_id=requirement_id,
                        provenance="declared_structured",
                        value=value,
                        quote=_quote(value),
                        locator={"source": "metadata", "key": key},
                    )
                )
            else:
                entries.append(
                    ProfileEntry(data_requirement_id=requirement_id, provenance="absent")
                )
        return entries

    # --- practice exercises (the package's own structure) -------------------------------

    def _practice_exercises(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        config_artifact = self._single_artifact(package, KIND_EXERCISE_CONFIG)
        if config_artifact is None:
            return ProfileEntry(data_requirement_id="practice_exercises", provenance="absent")

        config = _parse_json(fetcher.fetch(config_artifact.locator), config_artifact.locator)
        exercises = config.get("exercises") if isinstance(config, dict) else None
        if not isinstance(exercises, list):
            raise ExtractionError(f"artifact '{config_artifact.locator}' has no 'exercises' index")

        slugs = [str(e.get("slug", "")) for e in exercises if isinstance(e, dict)]
        instructions = self._instruction_bodies(package, fetcher)
        value = [
            {"exerciseId": slug, "hasInstructions": bool(instructions.get(slug, "").strip())}
            for slug in slugs
        ]
        return ProfileEntry(
            data_requirement_id="practice_exercises",
            provenance="declared_structured",
            value=value,
            quote=_quote(slugs),
            locator={
                "source": "artifact",
                "kind": KIND_EXERCISE_CONFIG,
                "locator": config_artifact.locator,
                "path": "$.exercises[*].slug",
            },
        )

    def _instruction_bodies(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> dict[str, str]:
        bodies: dict[str, str] = {}
        for artifact in package.artifacts:
            if artifact.kind != KIND_EXERCISE_INSTRUCTIONS:
                continue
            raw = fetcher.fetch(artifact.locator)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ExtractionError(
                    f"artifact '{artifact.locator}' is not UTF-8 text: {exc}"
                ) from exc
            bodies[_exercise_slug(artifact.locator)] = _strip_frontmatter(text)
        return bodies

    # --- extras: non-canonical but useful on the designer's workbench (ADR-0012) --------

    def _extras(self, package: PackageDTO, fetcher: PackageFetcherPort) -> tuple[ProfileExtra, ...]:
        manifest_artifact = self._single_artifact(package, KIND_MANIFEST)
        if manifest_artifact is None:
            return ()
        manifest = _parse_json(fetcher.fetch(manifest_artifact.locator), manifest_artifact.locator)
        if not isinstance(manifest, dict):
            raise ExtractionError(f"artifact '{manifest_artifact.locator}' is not a JSON object")
        extras = []
        for field in ("difficulty", "technologies"):
            if field in manifest:
                extras.append(
                    ProfileExtra(
                        name=field,
                        value=manifest[field],
                        quote=_quote(manifest[field]),
                        locator={
                            "source": "artifact",
                            "kind": KIND_MANIFEST,
                            "locator": manifest_artifact.locator,
                            "path": f"$.{field}",
                        },
                    )
                )
        return tuple(extras)

    @staticmethod
    def _single_artifact(package: PackageDTO, kind: str) -> ArtifactDTO | None:
        return next((a for a in package.artifacts if a.kind == kind), None)
