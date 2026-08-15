"""Admin CLI: `python -m app.cli seed | seed-workbench | set-role | import-learnpack |
register-package |
seed-demo | import-instrument | publish-instrument | bump-instrument | profile-content |
accept-extraction | reprofile | ratify-assessor | evaluate | declare-study |
update-study | open-study | sign-off-study | show-preview |
show-report | attribute-generator | register-generator | register-generator-version`.

The MVP has no rubric authoring UI: `LearnPack Pedagogical Rubric v1` is seeded straight
into a `published`, locked version (07-define.md, "Realización MVP"; 08-code.md §9).

`docs/seed/rubric-v1.json` stays the single source of truth — it is not duplicated inside
/backend. The seed therefore runs locally against Neon, never from the Render container.
"""

import argparse
import json
import logging
import re
import signal
import sys
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import BUILTIN_SOURCE_ROOT, get_settings
from app.modules.content_profiling.application.accept_extraction import (
    AcceptExtraction,
    AcceptExtractionCommand,
)
from app.modules.content_profiling.application.ports import PackageFetcherPort
from app.modules.content_profiling.application.profile_content import (
    ContentNotFound,
    NoAdapterForFormat,
    ProfileAlreadyExists,
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.domain.profile import ContentProfile, InvalidProfile
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import (
    FilesystemPackageFetcher,
    HttpPackageFetcher,
)
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluand_registry.application.attribute_generator import (
    AttributeGenerator,
    AttributeGeneratorCommand,
)
from app.modules.evaluand_registry.application.attribute_generator import (
    # Profiling has a same-named exception; both are imported here.
    ContentNotFound as UnregisteredContent,
)
from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnknownGeneratorVersion,
)
from app.modules.evaluand_registry.application.register_generator import (
    DuplicateGenerator,
    RegisterGenerator,
    RegisterGeneratorCommand,
    SimilarGeneratorExists,
)
from app.modules.evaluand_registry.application.register_generator_version import (
    DuplicateGeneratorVersion,
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
    UnknownGenerator,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
    RegisterPackageFromSource,
    RegisterPackageFromSourceCommand,
)
from app.modules.evaluand_registry.domain.content import (
    DEFAULT_VERSION,
    EDIT_PROVENANCES,
    GeneratorAlreadyAttributed,
    InvalidContent,
)
from app.modules.evaluand_registry.domain.generator import Generator, normalized_name
from app.modules.evaluand_registry.infrastructure import local_sources
from app.modules.evaluand_registry.infrastructure.acl_learnpack import (
    PACKAGE_FORMAT as LEARNPACK_FORMAT,
)
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    HttpPackageRoot,
    PackageDiscovery,
    PackageRoot,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.modules.evaluation.application.evaluate_content import (
    AssessorNotRatified,
    EvaluateContent,
    EvaluateContentCommand,
    InstrumentNotEvaluable,
    ProfileNotAvailable,
)
from app.modules.evaluation.application.preview_evaluation import (
    PreviewEvaluation,
    PreviewEvaluationCommand,
)
from app.modules.evaluation.application.ratify_assessor import (
    CoverageIncomplete,
    CriterionDelta,
    ForeignLineage,
    InstrumentVersionNotPublished,
    InstrumentVersionUnknown,
    RatificationNeedsConfirmation,
    RatifyAssessor,
    RatifyAssessorCommand,
)
from app.modules.evaluation.domain.model import InvalidAutomatedEvaluation
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, AssessorPackage
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.evaluation.infrastructure.gateways import (
    DesignInstrumentGateway,
    ProfilingGateway,
)
from app.modules.evaluation.infrastructure.preview_runs import RunStep, with_progress
from app.modules.evaluation.infrastructure.repository import (
    SqlAlchemyAutomatedEvaluationRepository,
    SqlAlchemyJudgmentRepository,
    SqlAlchemyRatificationRepository,
)
from app.modules.evaluation_design.application.import_instrument_draft import (
    ImportInstrumentDraft,
    ImportInstrumentDraftCommand,
    InstrumentImportError,
)
from app.modules.evaluation_design.application.publish_instrument import (
    InstrumentNotFound,
    PublishInstrument,
    PublishInstrumentCommand,
)
from app.modules.evaluation_design.domain.instrument import (
    InstrumentImmutable,
    InvalidInstrument,
)
from app.modules.evaluation_design.infrastructure.repository import (
    SqlAlchemyDataRequirementRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyReferenceDataRepository,
)
from app.modules.evaluation_studies.application.draft import (
    UNCHANGED,
    AssessorHasNotRatified,
    DeclareStudy,
    DeclareStudyCommand,
    InstrumentNotPublished,
    InstrumentRequiredFirst,
    SelectedScope,
    StudySelection,
    UnknownBrief,
    UnknownInstrument,
    UpdateStudyDraft,
    UpdateStudyDraftCommand,
)
from app.modules.evaluation_studies.application.draft import (
    # Aliased because two modules name the same concept in their own language, and the CLI
    # is the one adapter that speaks both: the registry raises `UnknownGenerator` when a
    # LINEAGE is missing, this one when a study's SCOPE names a version that does not exist.
    UnknownGenerator as ScopeNamesUnknownGenerator,
)
from app.modules.evaluation_studies.application.fitness import compute_fitness
from app.modules.evaluation_studies.application.gathering import gather_report_inputs
from app.modules.evaluation_studies.application.open_study import OpenStudy, OpenStudyCommand
from app.modules.evaluation_studies.application.report import compose_preview
from app.modules.evaluation_studies.application.sign_off_study import (
    SignOffStudy,
    SignOffStudyCommand,
)
from app.modules.evaluation_studies.domain.model import (
    ALL_GENERATORS,
    AssessorNotChosen,
    DatasetEmpty,
    DatasetLocked,
    GeneratorScopeNotDeclared,
    InstrumentNotChosen,
    InvalidStudy,
    Study,
    StudyAlreadyOpen,
    StudyAlreadySignedOff,
    StudyNotFound,
    StudyNotOpen,
)
from app.modules.evaluation_studies.infrastructure.gateways import (
    DesignGateway as StudiesDesignGateway,
)
from app.modules.evaluation_studies.infrastructure.gateways import (
    EvaluationGateway as StudiesEvaluationGateway,
)
from app.modules.evaluation_studies.infrastructure.gateways import (
    ProfilingGateway as StudiesProfilingGateway,
)
from app.modules.evaluation_studies.infrastructure.gateways import (
    RegistryGateway as StudiesRegistryGateway,
)
from app.modules.evaluation_studies.infrastructure.repository import (
    SqlAlchemyStudyReportRepository,
    SqlAlchemyStudyRepository,
)
from app.modules.identity.application.register_automated_assessor import (
    AutomatedAssessorDrifted,
    RegisterAutomatedAssessor,
    RegisterAutomatedAssessorCommand,
)
from app.modules.identity.domain.assessor import Assessor, InvalidAssessor, Role
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.modules.orchestration.application.commands import (
    AssignContent,
    AssignContentCommand,
    DuplicateAssignment,
    OpenCampaign,
    OpenCampaignCommand,
)
from app.modules.orchestration.infrastructure.repository import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyCampaignRepository,
)
from app.platform import batch_runs, observability, schema_version
from app.platform.db import SessionLocal
from app.platform.events import dispatcher
from app.platform.policies import register_all_policies
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher, HttpFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_FILE = REPO_ROOT / "docs" / "seed" / "rubric-v1.json"
DEFAULT_REFERENCE_FILE = REPO_ROOT / "docs" / "seed" / "pedagogical-reference.yaml"


def _rubric_version_id(rubric: dict[str, Any]) -> str:
    return f"{rubric['rubricId']}-{rubric['version']}"


def seed_rubric(session: Session, rubric: dict[str, Any]) -> None:
    """Upsert frameworks + the published rubric version + its criteria. Idempotent."""
    for framework in rubric["frameworks"]:
        session.execute(
            text(
                """
                INSERT INTO pedagogical_frameworks (id, citation)
                VALUES (:id, :citation)
                ON CONFLICT (id) DO UPDATE SET citation = excluded.citation
                """
            ),
            framework,
        )

    version_id = _rubric_version_id(rubric)
    scale = rubric["scale"]
    session.execute(
        text(
            """
            INSERT INTO rubric_versions
                (id, rubric_id, version, name, status, scope, scale_min, scale_max, published_at)
            VALUES
                (:id, :rubric_id, :version, :name, :status, :scope, :scale_min, :scale_max, now())
            ON CONFLICT (id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                scope = excluded.scope,
                scale_min = excluded.scale_min,
                scale_max = excluded.scale_max
            """
        ),
        {
            "id": version_id,
            "rubric_id": rubric["rubricId"],
            "version": rubric["version"],
            "name": rubric["name"],
            "status": rubric["status"],
            "scope": rubric["scope"],
            "scale_min": scale["min"],
            "scale_max": scale["max"],
        },
    )

    for criterion in rubric["criteria"]:
        session.execute(
            text(
                """
                INSERT INTO criteria
                    (rubric_version_id, criterion_id, ord, dimension, prompt, guidance,
                     anchor_low, anchor_high, qualities, grounded_in, eligible_sources)
                VALUES
                    (:rubric_version_id, :criterion_id, :ord, :dimension, :prompt, :guidance,
                     :anchor_low, :anchor_high, :qualities, :grounded_in, :eligible_sources)
                ON CONFLICT (rubric_version_id, criterion_id) DO UPDATE SET
                    ord = excluded.ord,
                    dimension = excluded.dimension,
                    prompt = excluded.prompt,
                    guidance = excluded.guidance,
                    anchor_low = excluded.anchor_low,
                    anchor_high = excluded.anchor_high,
                    qualities = excluded.qualities,
                    grounded_in = excluded.grounded_in,
                    eligible_sources = excluded.eligible_sources
                """
            ),
            {
                "rubric_version_id": version_id,
                "criterion_id": criterion["criterionId"],
                "ord": criterion["order"],
                "dimension": criterion["dimension"],
                "prompt": criterion["prompt"],
                "guidance": criterion["guidance"],
                "anchor_low": criterion.get("anchorLow", scale["anchorLow"]),
                "anchor_high": criterion.get("anchorHigh", scale["anchorHigh"]),
                "qualities": json.dumps(criterion["qualities"]),
                "grounded_in": json.dumps(criterion["groundedIn"]),
                "eligible_sources": json.dumps(criterion["eligibleSources"]),
            },
        )


def seed_reference_data(session: Session, reference: dict[str, Any]) -> None:
    """Upsert the norm-side reference data (design 12): dimensions, qualities, frameworks.

    Qualities are the stable column of the language — same anchor for new instruments and
    for the human reference panel (ADR-0015). Idempotent.
    """
    for framework in reference.get("frameworks", []):
        session.execute(
            text(
                """
                UPDATE pedagogical_frameworks
                   SET name = :name, scope_note = :scope_note
                 WHERE id = :id
                """
            ),
            {
                "id": framework["id"],
                "name": framework.get("name"),
                "scope_note": framework.get("scope_note"),
            },
        )
    for dimension in reference.get("dimensions", []):
        session.execute(
            text(
                """
                INSERT INTO pedagogical_dimensions (id, name)
                VALUES (:id, :name)
                ON CONFLICT (id) DO UPDATE SET name = excluded.name
                """
            ),
            {"id": dimension["id"], "name": dimension["name"]},
        )
    for quality in reference.get("qualities", []):
        session.execute(
            text(
                """
                INSERT INTO qualities (id, name, definition, dimension_id, grounded_in)
                VALUES (:id, :name, :definition, :dimension_id, cast(:grounded_in as jsonb))
                ON CONFLICT (id) DO UPDATE SET
                    name = excluded.name,
                    definition = excluded.definition,
                    dimension_id = excluded.dimension_id,
                    grounded_in = excluded.grounded_in
                """
            ),
            {
                "id": quality["id"],
                "name": quality["name"],
                "definition": quality["definition"],
                "dimension_id": quality["dimension"],
                "grounded_in": json.dumps(quality.get("grounded_in", [])),
            },
        )


def run_seed(seed_file: Path, reference_file: Path = DEFAULT_REFERENCE_FILE) -> None:
    rubric = json.loads(seed_file.read_text(encoding="utf-8"))
    reference = yaml.safe_load(reference_file.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        seed_rubric(session, rubric)
        seed_reference_data(session, reference)
        session.commit()

        criteria_count = session.execute(
            text("SELECT count(*) FROM criteria WHERE rubric_version_id = :id"),
            {"id": _rubric_version_id(rubric)},
        ).scalar_one()
        frameworks_count = session.execute(
            text("SELECT count(*) FROM pedagogical_frameworks")
        ).scalar_one()
        dimensions_count = session.execute(
            text("SELECT count(*) FROM pedagogical_dimensions")
        ).scalar_one()
        qualities_count = session.execute(text("SELECT count(*) FROM qualities")).scalar_one()

    print(
        f"seeded {rubric['name']} ({_rubric_version_id(rubric)}): "
        f"{criteria_count} criteria, {frameworks_count} frameworks, "
        f"{dimensions_count} dimensions, {qualities_count} qualities"
    )


def run_set_role(email: str, role: str) -> int:
    """Promote/demote an Assessor.

    `assessors.role` is the source of truth for authorisation, and only this command writes
    it — logging in never changes a role, so authentication cannot escalate privileges.
    """
    with SessionLocal() as session:
        repository = SqlAlchemyAssessorRepository(session)
        assessor = repository.get_by_email(email)
        if assessor is None:
            print(
                f"no assessor with email {email!r}. "
                "They must sign in once before a role can be assigned.",
                file=sys.stderr,
            )
            return 1
        try:
            assessor.assign_role(role)
        except InvalidAssessor as exc:
            print(str(exc), file=sys.stderr)
            return 1
        repository.update(assessor)
        session.commit()

    print(f"{email} is now {role}")
    return 0


def run_import_instrument(spec_file: Path, revise_definitions: bool = False) -> int:
    """Create or replace an instrument DRAFT from an authored YAML (13-code-qa §3.3).

    Publishing stays a separate, human act (`publish-instrument` or the admin endpoint):
    nothing produced by assistance reaches Published without one (design 12, inv. 5).
    `--revise-definitions` is the deliberate act that lets an existing data
    requirement's declaration — definition (ADR-0014) or value_domain (ADR-0020) —
    be changed in place; without it the lint blocks the import.
    """
    spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = ImportInstrumentDraft(
            instruments=SqlAlchemyInstrumentRepository(session),
            data_requirements=SqlAlchemyDataRequirementRepository(session),
            uow=uow,
        )
        try:
            result = use_case(
                ImportInstrumentDraftCommand(spec=spec, revise_definitions=revise_definitions)
            )
        except InstrumentImportError as exc:
            for problem in exc.problems:
                print(f"  LINT  {problem}", file=sys.stderr)
            return 1
        except (InvalidInstrument, InstrumentImmutable) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    for revision in result.revised_data_requirements:
        print(f"  REVISED {revision.id}:")
        if revision.old_definition != revision.new_definition:
            print(f"    old definition: {revision.old_definition}")
            print(f"    new definition: {revision.new_definition}")
        if revision.old_value_domain != revision.new_value_domain:
            print(f"    old value_domain: {json.dumps(revision.old_value_domain, sort_keys=True)}")
            print(f"    new value_domain: {json.dumps(revision.new_value_domain, sort_keys=True)}")
    instrument = result.instrument
    minted = (
        f", minted data requirements: {', '.join(result.minted_data_requirements)}"
        if result.minted_data_requirements
        else ""
    )
    revised = (
        f", revised definitions: {', '.join(r.id for r in result.revised_data_requirements)}"
        if result.revised_data_requirements
        else ""
    )
    print(
        f"draft {instrument.id}: {len(instrument.claims)} claims, "
        f"{len(instrument.criteria)} criteria, "
        f"{len(instrument.bindings)} binding(s){minted}{revised}"
    )
    return 0


def run_publish_instrument(instrument_version_id: str, email: str) -> int:
    """The human act: publish a draft, validating the full evidential argument."""
    with SessionLocal() as session:
        assessor = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if assessor is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1
        uow = UnitOfWork(session)
        use_case = PublishInstrument(
            instruments=SqlAlchemyInstrumentRepository(session),
            data_requirements=SqlAlchemyDataRequirementRepository(session),
            reference=SqlAlchemyReferenceDataRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        try:
            instrument = use_case(
                PublishInstrumentCommand(
                    instrument_version_id=instrument_version_id, published_by=assessor.id
                )
            )
        except (InstrumentNotFound, InstrumentImmutable, InvalidInstrument) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print(f"published {instrument.id} (by {email})")
    return 0


_VERSION_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _next_version(version: str) -> str | None:
    """v1 -> v2; None when the scheme is not v<n> (the caller then requires --to)."""
    match = re.fullmatch(r"v(\d+)", version)
    return f"v{int(match.group(1)) + 1}" if match else None


def _replace_top_level_entry(source: str, key: str, entry_line: str) -> str | None:
    """Textually replace a top-level YAML entry (key line + indented continuation,
    covering block scalars) with `entry_line`; if the key is absent, insert the line
    right after the top-level `version:` entry. None when neither anchor exists."""
    lines = source.splitlines()
    trailing_newline = "\n" if source.endswith("\n") else ""
    key_pattern = re.compile(rf"^{re.escape(key)}:(\s|$)")

    for index, line in enumerate(lines):
        if not key_pattern.match(line):
            continue
        end = index + 1
        while end < len(lines):
            if lines[end].startswith((" ", "\t")):
                end += 1
            elif (
                lines[end].strip() == ""
                and end + 1 < len(lines)
                and lines[end + 1].startswith((" ", "\t"))
            ):
                end += 1  # blank line inside the block, not a separator
            else:
                break
        return "\n".join(lines[:index] + [entry_line] + lines[end:]) + trailing_newline

    for index, line in enumerate(lines):
        if re.match(r"^version:(\s|$)", line):
            return "\n".join(lines[: index + 1] + [entry_line] + lines[index + 1 :]) + (
                trailing_newline
            )
    return None


def run_bump_instrument(spec_file: Path, to_version: str | None, reason: str | None) -> int:
    """Clone an instrument YAML into the next version's file — textually, so the
    header comments and block-scalar style survive (they are part of the authored
    artifact; a parse/dump round-trip would destroy them). Writes the new file only;
    importing and publishing stay separate acts."""
    source_text = spec_file.read_text(encoding="utf-8")
    try:
        spec = yaml.safe_load(source_text)
    except yaml.YAMLError as exc:
        print(f"cannot parse {spec_file}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(spec, dict) or "instrument_id" not in spec or "version" not in spec:
        print(f"{spec_file} has no top-level instrument_id/version", file=sys.stderr)
        return 1
    instrument_id = str(spec["instrument_id"])
    old_version = str(spec["version"])

    new_version = to_version or _next_version(old_version)
    if new_version is None:
        print(
            f"cannot infer the next version from {old_version!r} (expected v<n>): pass --to",
            file=sys.stderr,
        )
        return 1
    if new_version == old_version:
        print(f"target version equals the current one ({old_version})", file=sys.stderr)
        return 1
    if not _VERSION_COMPONENT.fullmatch(new_version):
        print(
            f"invalid target version {new_version!r} (allowed: letters, digits, '.', '_', '-')",
            file=sys.stderr,
        )
        return 1

    target_file = spec_file.with_name(f"{instrument_id}-{new_version}.yaml")
    if target_file.exists():
        print(f"target file already exists: {target_file}", file=sys.stderr)
        return 1

    new_id = f"{instrument_id}-{new_version}"
    with SessionLocal() as session:  # read-only: collision check + source status
        repository = SqlAlchemyInstrumentRepository(session)
        existing = repository.get(new_id)
        if existing is not None:
            print(
                f"instrument version {new_id} already exists in the db ({existing.status})",
                file=sys.stderr,
            )
            return 1
        source_in_db = repository.get(f"{instrument_id}-{old_version}")

    transformed = _replace_top_level_entry(source_text, "version", f"version: {new_version}")
    if transformed is None:
        print(f"no top-level 'version:' line found in {spec_file}", file=sys.stderr)
        return 1
    if reason is not None:
        transformed = _replace_top_level_entry(
            transformed, "revision_reason", f"revision_reason: {json.dumps(reason)}"
        )
        if transformed is None:  # unreachable once version replaced; belt and braces
            print(f"cannot place revision_reason in {spec_file}", file=sys.stderr)
            return 1

    # Self-check before writing: the textual edit must round-trip to exactly the
    # intended spec — never write an unverified file.
    try:
        check = yaml.safe_load(transformed)
    except yaml.YAMLError:
        check = None
    if (
        not isinstance(check, dict)
        or check.get("instrument_id") != instrument_id
        or check.get("version") != new_version
        or (reason is not None and check.get("revision_reason") != reason)
    ):
        print(
            "textual bump produced an unexpected result; nothing written — bump by hand",
            file=sys.stderr,
        )
        return 1

    target_file.write_text(transformed, encoding="utf-8")
    print(f"wrote {target_file} ({instrument_id} {old_version} -> {new_version})")
    status = source_in_db.status if source_in_db is not None else "not imported"
    print(f"source {instrument_id}-{old_version} in db: {status}")
    print("next steps:")
    print("  1. review the new file (update header comments that mention the old version)")
    print(f"  2. python -m app.cli import-instrument --file {target_file}")
    print(f"  3. python -m app.cli publish-instrument --id {new_id} --email <admin>")
    return 0


# ------------------------------------------------------------- automated evaluation


def _assessor_package(name: str, version: str) -> AssessorPackage | None:
    package = AUTOMATED_ASSESSORS.get((name, version))
    if package is None:
        known = ", ".join(f"{n}:{v}" for n, v in sorted(AUTOMATED_ASSESSORS))
        print(f"unknown assessor {name}:{version} (registry has: {known})", file=sys.stderr)
    return package


def _assessor_from_spec(spec: str | None) -> AssessorPackage | None:
    """`name:version` -> the package. Always explicit: an assessor owes itself to a lineage,
    and naming which one is doing the judging is part of the act."""
    if spec is None or ":" not in spec:
        known = ", ".join(f"{n}:{v}" for n, v in sorted(AUTOMATED_ASSESSORS))
        print(f"pass --assessor <name>:<version> (registry has: {known})", file=sys.stderr)
        return None
    name, version = spec.split(":", 1)
    return _assessor_package(name, version)


def _print_decided_deltas(deltas: tuple[CriterionDelta, ...], email: str) -> None:
    """The half of the diff that needed no decision from the caller, as it was decided."""
    for delta in deltas:
        if delta.disposition == "abstained":
            print(f"  {delta.change:8} {delta.criterion_id}: abstained (no confirm needed)")
        elif delta.disposition == "confirmed":
            print(f"  {delta.change:8} {delta.criterion_id}: confirmed by {email}")


def run_ratify_assessor(
    name: str, version: str, instrument_version_id: str, email: str, confirmed: list[str]
) -> int:
    """The ADR-0019 act: make one instrument version evaluable by one assessor.

    Composition only (ADR-0036 §3): Identity mints the assessor row, Evaluation records
    the ratification, both in this session's transaction. The rules live in the two use
    cases, which the console calls too; what belongs here is turning each refusal into the
    line and the exit code a terminal expects.

    Initial registration IS the first ratification. Against a later version of the same
    lineage, the diff is computed mechanically (literal pass_condition + required_data):
    unchanged criteria carry their coverage over; changed/new EXECUTED criteria demand an
    explicit `--confirm <criterion_id>`; changed abstained ones are informational (an
    abstention realizes no normative text)."""
    package = _assessor_package(name, version)
    if package is None:
        return 1

    with SessionLocal() as session:
        assessors = SqlAlchemyAssessorRepository(session)
        admin = assessors.get_by_email(email)
        if admin is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1

        try:
            registered = RegisterAutomatedAssessor(assessors)(
                RegisterAutomatedAssessorCommand(
                    name=package.name,
                    version=package.version,
                    display_name=package.display_name,
                    source_config=package.source_config,
                )
            )
        except AutomatedAssessorDrifted as exc:
            print(str(exc), file=sys.stderr)
            return 1

        ratify = RatifyAssessor(
            instruments=DesignInstrumentGateway(session),
            ratifications=SqlAlchemyRatificationRepository(session),
            uow=UnitOfWork(session),
        )
        try:
            result = ratify(
                RatifyAssessorCommand(
                    assessor_id=registered.assessor.assessor_id,
                    instrument_id=package.instrument_id,
                    instrument_version_id=instrument_version_id,
                    coverage=package.coverage,
                    ratified_by=admin.id,
                    confirmed=frozenset(confirmed),
                )
            )
        except InstrumentVersionUnknown as exc:
            print(f"instrument version {exc.instrument_version_id} not found", file=sys.stderr)
            return 1
        except ForeignLineage as exc:
            print(
                f"{name}:{version} owes itself to lineage '{exc.expected_instrument_id}', "
                f"not '{exc.actual_instrument_id}' (ADR-0019)",
                file=sys.stderr,
            )
            return 1
        except InstrumentVersionNotPublished as exc:
            print(
                f"{exc.instrument_version_id} is {exc.status}: ratification requires a "
                "published version - calibrate drafts with `evaluate --dry-run`",
                file=sys.stderr,
            )
            return 1
        except CoverageIncomplete as exc:
            print(
                "coverage does not decide every criterion of the version: "
                f"{', '.join(sorted(exc.undecided))} - executing or abstaining is a change "
                "of the artifact, i.e. a new assessor version (ADR-0016)",
                file=sys.stderr,
            )
            return 1
        except RatificationNeedsConfirmation as exc:
            _print_decided_deltas(exc.deltas, email)
            print(
                "executed criteria changed since the last ratified version "
                f"({exc.previous_version_id}) - confirm the executor still realizes each "
                "text with: " + " ".join(f"--confirm {d.criterion_id}" for d in exc.pending),
                file=sys.stderr,
            )
            return 1

        # Printed once the act has gone through: nothing is committed until it does, so a
        # registration announced beside a refusal would be announcing a row that is gone.
        if registered.newly_registered:
            print(
                f"registered automated assessor {package.display_name} "
                f"({registered.assessor.assessor_id})"
            )
        _print_decided_deltas(result.deltas, email)

    if not result.newly_ratified:
        print(f"{name}:{version} already ratified {instrument_version_id}")
    else:
        print(f"ratified {instrument_version_id} for {name}:{version} (by {email})")
    return 0


def run_evaluate(
    raw_content_id: str, instrument_version_id: str, assessor_spec: str | None, dry_run: bool
) -> int:
    """Evaluate a content's profile with an automated assessor - or preview it.

    `--dry-run` (the calibration loop): accepts drafts, needs no ratification, and
    persists NOTHING - no evaluation, no events, no judgment."""
    try:
        content_id = UUID(raw_content_id)
    except ValueError:
        print(f"invalid content id: {raw_content_id}", file=sys.stderr)
        return 1
    package = _assessor_from_spec(assessor_spec)
    if package is None:
        return 1
    assessor_name, assessor_version = package.name, package.version

    with SessionLocal() as session:
        instruments = DesignInstrumentGateway(session)
        profiles = ProfilingGateway(session)
        if dry_run:
            # The scriptable half of the calibration loop gets what the page gets: each
            # criterion announced as it lands (to stderr, so stdout stays the report) and
            # every LLM attempt written to the run's trace file.
            trace = observability.trace_path(f"cli-{new_id()}")
            preview_use_case = PreviewEvaluation(
                instruments=instruments,
                profiles=profiles,
                coverage=package.coverage,
                executors=with_progress(package.executors, _print_step),
            )
            sinks = [_print_call]
            if trace is not None:
                sinks.append(observability.jsonl_sink(trace))
            sink = observability.fan_out(*sinks)
            # This run's own memory of what it asked, so nothing of an earlier one leaks
            # into its spend or its trace.
            scope = package.cache_scope() if package.cache_scope else nullcontext()
            try:
                with scope, observability.collecting(sink):
                    preview = preview_use_case(
                        PreviewEvaluationCommand(
                            content_id=content_id, instrument_version_id=instrument_version_id
                        )
                    )
            except (InstrumentNotEvaluable, ProfileNotAvailable) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except AssessorExecutionError as exc:
                print(
                    f"too many criteria failed to judge - past the failure budget the run "
                    f"was not an evaluation (ADR-0037): {exc}\n"
                    "nothing persisted - fix the cause (or just retry, if it was "
                    "transient) and run evaluate again",
                    file=sys.stderr,
                )
                if trace is not None:
                    print(f"the prompts and raw answers are in {trace}", file=sys.stderr)
                return 1
            _print_outcomes(preview.outcomes, preview.judgment)
            print("dry run: nothing persisted (no evaluation, no events, no judgment)")
            if trace is not None and trace.exists():
                print(f"LLM trace: {trace}")
            return 0

        assessor = SqlAlchemyAssessorRepository(session).get_automated(
            assessor_name, assessor_version
        )
        if assessor is None:
            print(
                f"{assessor_name}:{assessor_version} is not registered - run ratify-assessor first",
                file=sys.stderr,
            )
            return 1
        uow = UnitOfWork(session)
        use_case = EvaluateContent(
            evaluations=SqlAlchemyAutomatedEvaluationRepository(session),
            instruments=instruments,
            profiles=profiles,
            ratifications=SqlAlchemyRatificationRepository(session),
            coverage=package.coverage,
            executors=dict(package.executors),
            publisher=uow.events,
            uow=uow,
        )
        try:
            evaluation = use_case(
                EvaluateContentCommand(
                    content_id=content_id,
                    instrument_version_id=instrument_version_id,
                    assessor_id=assessor.id,
                )
            )
        except (
            InstrumentNotEvaluable,
            AssessorNotRatified,
            ProfileNotAvailable,
            InvalidAutomatedEvaluation,
        ) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except AssessorExecutionError as exc:
            # ADR-0037 §3: below the failure budget the derivation absorbed the failures
            # as execution_error rows, so reaching here means the budget was exceeded and
            # the run aborts whole. The exception fired before anything was added to the
            # session, so there is nothing to roll back.
            print(
                f"too many criteria failed to judge - past the failure budget the run "
                f"was not an evaluation (ADR-0037): {exc}\n"
                "nothing persisted - fix the cause (or just retry, if it was "
                "transient) and run evaluate again",
                file=sys.stderr,
            )
            return 1

        print(
            f"evaluation {evaluation.id} (attempt {evaluation.attempt}, "
            f"assessor {package.display_name})"
        )
        # The judgment policy ran synchronously post-commit; show what it derived.
        judgments = SqlAlchemyJudgmentRepository(session).list_for_contents(
            [content_id], instrument_version_id
        )
        current = next((j for j in reversed(judgments) if j.evaluation_id == evaluation.id), None)
        outcome_counts: dict[str, int] = {}
        for outcome in evaluation.outcomes:
            outcome_counts[outcome.outcome] = outcome_counts.get(outcome.outcome, 0) + 1
        print("outcomes: " + ", ".join(f"{k}={v}" for k, v in sorted(outcome_counts.items())))
        if current is not None:
            for claim in current.claims:
                print(f"  {claim.status:12} {claim.claim_id}")
            excluded = current.coverage.get("excludedClaims", [])
            if excluded:
                print(f"  excluded (all not_applicable): {', '.join(excluded)}")
    return 0


def _print_step(step: RunStep) -> None:
    """A dry run's progress, on stderr: stdout stays the report a script reads."""
    print(f"  [{step.duration_ms / 1000:6.1f}s] {step.label}: {step.detail}", file=sys.stderr)


def _print_call(call: observability.LlmCall) -> None:
    spent = call.error or f"{call.tokens_in}->{call.tokens_out} tokens"
    print(
        f"  [{call.latency_ms / 1000:6.1f}s] {call.task_id or 'llm call'} "
        f"attempt {call.attempt}: {spent}",
        file=sys.stderr,
    )


def _print_outcomes(outcomes, judgment) -> None:  # noqa: ANN001 — CLI presentation only
    width = max(len(o.criterion_id) for o in outcomes)
    state_width = max(len(o.outcome) for o in outcomes)
    for outcome in outcomes:
        origin = "derived " if outcome.derived else "executed"
        detail = ""
        if outcome.failure_mode:
            detail = f"  [{outcome.failure_mode}]"
        elif outcome.execution_cause:
            cause = outcome.execution_cause
            detail = f"  [{cause.kind}: {cause.message}]"
        elif outcome.quote:
            quote = outcome.quote.replace("\n", " ")
            detail = f'  "{quote[:60]}..."' if len(quote) > 60 else f'  "{quote}"'
        print(f"  {outcome.criterion_id:{width}}  {outcome.outcome:{state_width}} {origin}{detail}")
    print("claims:")
    for claim in judgment.claims:
        basis = ", ".join(f"{k}={v}" for k, v in claim.evidence_basis.items() if v)
        print(f"  {claim.status:12} {claim.claim_id}  ({basis})")
    excluded = judgment.coverage.get("excludedClaims", [])
    if excluded:
        print(f"  excluded (all not_applicable): {', '.join(excluded)}")


# ----------------------------------------------------------------- content profiling


def _package_fetcher(base_dir: Path | None) -> PackageFetcherPort:
    """HTTP against real packages; `--base-dir` resolves locators as local paths."""
    return FilesystemPackageFetcher(base_dir) if base_dir else HttpPackageFetcher()


def _build_profile_content(session: Session, base_dir: Path | None) -> ProfileContent:
    uow = UnitOfWork(session)
    return ProfileContent(
        profiles=SqlAlchemyProfileRepository(session),
        contents=RegistryContentGateway(session),
        namespace=DesignNamespaceGateway(session),
        adapters=ADAPTERS_BY_FORMAT,
        fetcher=_package_fetcher(base_dir),
        publisher=uow.events,
        uow=uow,
    )


def _describe_profile(profile: ContentProfile) -> str:
    if profile.status == "failed":
        return f"FAILED {profile.content_id}: {profile.error}"
    absent = sum(1 for e in profile.entries if e.provenance == "absent")
    return (
        f"ok {profile.content_id}: {len(profile.entries)} entries "
        f"({absent} absent), {len(profile.extras)} extras "
        f"[adapter {profile.package_format}/{profile.adapter_version}]"
    )


def run_profile_content(raw_content_id: str, base_dir: Path | None) -> int:
    """Manual profiling — works without an acceptance: this is how the samples that earn
    the `ExtractionAccepted` act are produced (13-code-qa §3.4)."""
    try:
        content_id = UUID(raw_content_id)
    except ValueError:
        print(f"not a content id: {raw_content_id!r}", file=sys.stderr)
        return 1
    with SessionLocal() as session:
        use_case = _build_profile_content(session, base_dir)
        try:
            profile = use_case(ProfileContentCommand(content_id=content_id))
        except ProfileAlreadyExists as exc:
            print(str(exc))
            return 0
        except (ContentNotFound, NoAdapterForFormat, InvalidProfile) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(_describe_profile(profile))
    return 0


def run_accept_extraction(package_format: str, email: str) -> int:
    """The human act (ADR-0012): accept the CURRENT adapter version for a format."""
    adapter = ADAPTERS_BY_FORMAT.get(package_format)
    if adapter is None:
        known = ", ".join(sorted(ADAPTERS_BY_FORMAT)) or "none"
        print(
            f"no extraction adapter for {package_format!r} (registered: {known})",
            file=sys.stderr,
        )
        return 1
    with SessionLocal() as session:
        assessor = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if assessor is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1
        uow = UnitOfWork(session)
        use_case = AcceptExtraction(
            acceptances=SqlAlchemyAcceptanceRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        newly = use_case(
            AcceptExtractionCommand(
                package_format=package_format,
                adapter_version=adapter.adapter_version,
                accepted_by=assessor.id,
            )
        )
    verdict = "accepted" if newly else "was already accepted"
    print(f"extraction {package_format}/{adapter.adapter_version} {verdict} (by {email})")
    return 0


def run_reprofile(
    package_format: str, raw_content_ids: list[str] | None, base_dir: Path | None
) -> int:
    """Explicit batch re-profiling — never a cascade (12-define). One transaction per
    content; contents already profiled ok by the current adapter version are skipped."""
    if package_format not in ADAPTERS_BY_FORMAT:
        print(f"no extraction adapter for {package_format!r}", file=sys.stderr)
        return 1
    try:
        selected = [UUID(raw) for raw in raw_content_ids or []]
    except ValueError as exc:
        print(f"not a content id: {exc}", file=sys.stderr)
        return 1
    if not selected:
        with SessionLocal() as session:
            selected = RegistryContentGateway(session).list_content_ids(package_format)

    profiled = failed = skipped = errors = 0
    for content_id in selected:
        with SessionLocal() as session:
            use_case = _build_profile_content(session, base_dir)
            try:
                profile = use_case(ProfileContentCommand(content_id=content_id))
            except ProfileAlreadyExists:
                skipped += 1
                continue
            except (ContentNotFound, NoAdapterForFormat, InvalidProfile) as exc:
                print(f"  ERROR {content_id}: {exc}", file=sys.stderr)
                errors += 1
                continue
        print(f"  {_describe_profile(profile)}")
        profiled += profile.status == "ok"
        failed += profile.status == "failed"
    print(
        f"reprofiled {package_format}: {profiled} ok, {failed} failed, "
        f"{skipped} skipped, {errors} errors"
    )
    return 0 if errors == 0 else 1


def run_attribute_generator(content_id: UUID, generator_version_id: UUID, email: str) -> int:
    """The repair act (ADR-0024): record a generator learnt after registration."""
    with SessionLocal() as session:
        assessor = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if assessor is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1
        uow = UnitOfWork(session)
        use_case = AttributeGenerator(
            contents=SqlAlchemyContentRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        try:
            content = use_case(
                AttributeGeneratorCommand(
                    content_id=content_id,
                    generator_version_id=generator_version_id,
                    attributed_by=assessor.id,
                )
            )
        except (UnregisteredContent, UnknownGeneratorVersion, GeneratorAlreadyAttributed) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print(f"attributed {content.external_id} to generator {generator_version_id} (by {email})")
    return 0


# ------------------------------------------------------------------- delete-content
# A development affordance, not a capability of the system (ADR-0033).

# What "used" means, and why each one is asked. The last two are the reason this is a command
# with a check rather than a DELETE in a runbook: `study_dataset` and `study_recipe` carry ids
# with no foreign key (ADR-0006), so the database would let the deletion succeed and rot.
_CONTENT_USES = (
    ("evaluations", "content_id", "it has been evaluated"),
    ("assignments", "content_id", "it is assigned to an evaluator"),
    ("campaign_contents", "content_id", "it is part of a campaign"),
    ("content_evaluation_completions", "content_id", "it has completed quorum"),
    ("study_dataset", "content_id", "a study's dataset names it"),
)


def _content_uses(session: Session, content_id: UUID, brief_id: UUID | None) -> list[str]:
    """Everything standing in the way, all of it, so one run tells the whole story."""
    blocking = [
        f"{reason} ({table})"
        for table, column, reason in _CONTENT_USES
        if session.execute(
            text(f"SELECT 1 FROM {table} WHERE {column} = :id LIMIT 1"),  # noqa: S608 — literals
            {"id": content_id},
        ).scalar()
    ]
    if (
        brief_id is not None
        and session.execute(
            text("SELECT 1 FROM study_recipe WHERE brief_id = :id LIMIT 1"), {"id": brief_id}
        ).scalar()
    ):
        blocking.append("a study's recipe names its brief (study_recipe)")
    return blocking


def run_delete_content(content_id: UUID) -> int:
    """Remove a content version that nothing has used (ADR-0033).

    Local mode only, and `Settings` refuses that unless the database is local (ADR-0008), so
    the single condition below is the whole guard — the same reasoning `seed-demo` documents.

    The deletion is short precisely because the refusal is strict: unused content has no
    evaluations, assignments, campaigns or studies to clean up, so what is left is its
    profiles, itself, an orphaned brief and their events. One transaction, so a refusal
    halfway through leaves nothing behind.
    """
    if not get_settings().is_local_auth:
        print(
            "delete-content only runs with AUTH_MODE=local: registered content is never "
            "removed from a real store, because a published study report is immutable and "
            "freezes what it evaluated (ADR-0033).",
            file=sys.stderr,
        )
        return 1

    with SessionLocal() as session:
        row = session.execute(
            text("SELECT external_id, version, brief_id FROM contents WHERE id = :id"),
            {"id": content_id},
        ).one_or_none()
        if row is None:
            print(f"no content with id {content_id}", file=sys.stderr)
            return 1
        external_id, version, brief_id = row

        blocking = _content_uses(session, content_id, brief_id)
        if blocking:
            print(
                f"{external_id} v{version} has been used and is not removable:\n  "
                + "\n  ".join(blocking),
                file=sys.stderr,
            )
            return 1

        # Orphaned means orphaned AFTER this deletion: the same brief may be another
        # content's, which is the paired design rather than an accident (ADR-0013).
        orphaned_brief = (
            brief_id is not None
            and not session.execute(
                text("SELECT 1 FROM contents WHERE brief_id = :b AND id <> :c LIMIT 1"),
                {"b": brief_id, "c": content_id},
            ).scalar()
        )

        profiles = session.execute(
            text("SELECT count(*) FROM content_profiles WHERE content_id = :id"),
            {"id": content_id},
        ).scalar()
        artifacts = session.execute(
            text("SELECT count(*) FROM content_package_artifacts WHERE content_id = :id"),
            {"id": content_id},
        ).scalar()

        # `profile_entries` and `profile_extras` cascade from the profile.
        session.execute(
            text("DELETE FROM content_profiles WHERE content_id = :id"), {"id": content_id}
        )
        # `content_package_artifacts` cascades from the content.
        session.execute(text("DELETE FROM contents WHERE id = :id"), {"id": content_id})
        if orphaned_brief:
            session.execute(text("DELETE FROM generation_briefs WHERE id = :id"), {"id": brief_id})
        # `events.aggregate_id` is text, not uuid: the id travels as a string or Postgres
        # refuses to compare it at all.
        aggregates = [str(content_id)] + ([str(brief_id)] if orphaned_brief else [])
        events = session.execute(
            text("DELETE FROM events WHERE aggregate_id = ANY(:ids)"), {"ids": aggregates}
        ).rowcount
        session.commit()

    brief_note = "1 orphaned brief" if orphaned_brief else "brief kept (another content shares it)"
    print(
        f"deleted {external_id} v{version}: {profiles} profile(s), {artifacts} artifact(s), "
        f"{events} event(s), {brief_note}"
    )
    return 0


def run_register_generator(name: str, distinct_from: str | None) -> int:
    """Mint a generator lineage (ADR-0031 §3) — the rare act, and the only one that still
    takes a typed name, hence the only one guarded against a near miss."""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = RegisterGenerator(
            generators=SqlAlchemyGeneratorRepository(session), publisher=uow.events, uow=uow
        )
        try:
            generator = use_case(
                RegisterGeneratorCommand(name=name, confirm_distinct_from=distinct_from)
            )
        except SimilarGeneratorExists as exc:
            print(str(exc), file=sys.stderr)
            print(
                f"  re-run with --distinct-from {exc.existing!r} if it really is another generator",
                file=sys.stderr,
            )
            return 1
        except DuplicateGenerator as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print(f"registered generator {generator.name} ({generator.id})")
    return 0


def run_register_generator_version(
    generator_id: UUID | None, generator_name: str | None, version: str, changelog: str | None
) -> int:
    """Register a version under a generator (ADR-0031 §3) — the routine act, the one the
    genetic-algorithm loop runs many times per generation."""
    with SessionLocal() as session:
        generators = SqlAlchemyGeneratorRepository(session)
        if generator_id is None:
            assert generator_name is not None  # argparse guarantees one of the two
            # Resolves, never mints: creating a lineage is the other command, on purpose.
            found = generators.find_by_name_key(normalized_name(generator_name))
            if found is None:
                print(
                    f"no generator named {generator_name!r} — register it first with "
                    "register-generator",
                    file=sys.stderr,
                )
                return 1
            generator_id = found.id

        uow = UnitOfWork(session)
        use_case = RegisterGeneratorVersion(
            generators=generators,
            versions=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        try:
            registered = use_case(
                RegisterGeneratorVersionCommand(
                    generator_id=generator_id,
                    version=version,
                    # An empty flag declares nothing; it must not write an empty key (ADR-0030).
                    metadata={"changelog": changelog} if changelog else {},
                )
            )
        except (UnknownGenerator, DuplicateGeneratorVersion) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    print(f"registered version {registered.version} ({registered.id})")
    return 0


def _generator_declaration(value: str) -> str:
    """`--generator` takes a generator version id or the literal `unknown` (ADR-0024).
    Validated at parse time so a typo fails before anything is registered."""
    if value == "unknown":
        return value
    try:
        return str(UUID(value))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a generator version id or 'unknown', got {value!r}"
        ) from None


def run_import_learnpack(seed_file: Path, base_dir: Path | None = None) -> int:
    """Bulk-register courses from a canonical JSON list, reusing `RegisterContentVersion`.

    For registering from a package source (a URL or a local course directory) use
    `register-package` instead — this command is for hand-composed batches that already
    carry their artifact lists. `--base-dir` resolves artifact locators on the filesystem
    (local packages); without it the intake fetches over HTTP (ADR-0022).
    """
    raw_courses = json.loads(seed_file.read_text(encoding="utf-8"))
    if not isinstance(raw_courses, list):
        print("the file must contain a JSON list of courses", file=sys.stderr)
        return 1

    fetcher = FilesystemFetcher(base_dir) if base_dir else HttpFetcher()
    created = duplicated = failed = 0
    for raw in raw_courses:
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            use_case = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
                brief_intake=PackageBriefIntake(fetcher),
            )
            try:
                command = RegisterContentVersionCommand(
                    package_format=raw["package_format"],
                    external_id=raw["external_id"],
                    # Optional (ADR-0028): an entry with no deployed instance omits the key.
                    consumable_url=raw.get("consumable_url"),
                    version=str(raw.get("version", "1")),
                    artifacts=raw.get("artifacts", []),
                    brief_id=UUID(raw["brief_id"]) if raw.get("brief_id") else None,
                    # Required key (ADR-0024): a missing one is a KeyError, caught
                    # below as a counted INVALID row — declared per entry or not at all.
                    generator_version_id=(
                        UUID(raw["generator_version_id"]) if raw["generator_version_id"] else None
                    ),
                    edit_provenance=raw.get("edit_provenance", "unknown"),
                )
                content = use_case(command)
                created += 1
                print(f"  created  {content.external_id} v{content.version}")
            except DuplicateContent:
                duplicated += 1
                print(
                    f"  skipped  {raw.get('external_id') or raw.get('slug')} (already registered)"
                )
            except (InvalidContent, KeyError, UnknownGeneratorVersion, ValueError) as exc:
                failed += 1
                print(
                    f"  INVALID  {raw.get('external_id') or raw.get('slug')}: {exc}",
                    file=sys.stderr,
                )

    print(f"\n{created} created, {duplicated} already present, {failed} invalid")
    return 1 if failed else 0


# ------------------------------------------------------------------- register-package
# Discovery-based intake (ADR-0027): humans declare a source, never an artifact list.


class _UndeclaredRoot(Exception):
    """A path, or a `--root` key, that no declared source root covers (ADR-0035 §1)."""


def _declared_root(key: str) -> local_sources.SourceRoot:
    """The tree `--root` names, or a refusal listing the ones that exist.

    A root is declared in the environment and mounted when the app assembles, so naming one
    the process does not serve is two different mistakes with one symptom — never declared,
    or declared after the server started. The message says both, because the operator cannot
    tell them apart from here.
    """
    root = local_sources.root_for(key)
    if root is None:
        declared = ", ".join(r.key for r in local_sources.configured_roots())
        raise _UndeclaredRoot(
            f"no source root named '{key}' (declared: {declared}) — add it to "
            "LOCAL_SOURCE_ROOTS as '<key>=<folder>' and restart the API, which is what "
            "mounts it (see backend/README.md)"
        )
    return root


def _root_holding(directory: Path) -> tuple[local_sources.SourceRoot, str]:
    """The declared root a path lives under, and the path relative to it.

    Locators are minted into that root's mount, so a package outside every declared tree has
    no honest registration available: it would register locators nobody can fetch, and the
    brief intake and profiling would degrade into absences later (ADR-0035 §1). Refusing here
    is the same call the mount preflight makes one step further down.
    """
    resolved = directory.resolve()
    for root in local_sources.configured_roots():
        if not root.exists:
            continue
        base = root.path.resolve()
        if resolved == base or base in resolved.parents:
            return root, resolved.relative_to(base).as_posix()
    declared = ", ".join(r.key for r in local_sources.configured_roots())
    raise _UndeclaredRoot(
        f"'{directory}' is not under any declared source root (declared: {declared}) — "
        "put it under courses/, or declare its tree in LOCAL_SOURCE_ROOTS and restart the "
        "API (see backend/README.md)"
    )


def _course_root(course_dir: Path) -> FilesystemPackageRoot:
    """A local course's root: locators are minted into the mount that serves its tree, so the
    registered package behaves exactly like an http-served one for fetching (brief intake,
    profiling). It does not make the course consumable: a local course registers with no
    consumable URL (ADR-0028)."""
    root, relative = _root_holding(course_dir)
    return local_sources.package_root(root, relative)


def _mount_preflight(root: FilesystemPackageRoot, course_dir: Path) -> bool:
    """One GET through the mount before registering. Registered locators point into it, so
    registering with the API down would not fail — it would degrade into absent briefs and
    failing profiles. Loud refusal instead.

    The probe is a file this course actually has, picked off disk: what is being checked is
    that the mount serves *this tree*, which is true of every format. Probing a named
    manifest would make the check format-specific, and it would refuse every format whose
    convention does not happen to use that name."""
    probe = next((p for p in sorted(course_dir.rglob("*")) if p.is_file()), None)
    if probe is None:
        return True  # nothing to serve; discovery will refuse it with a better message
    locator = root.locator_for(probe.relative_to(course_dir).as_posix())
    try:
        HttpFetcher().fetch(locator)
        return True
    except FetchError as exc:
        print(
            f"the dev mount does not serve this course ({exc}).\n"
            "Start the API with AUTH_MODE=local: registered locators point into "
            f"{locator}, so without it the brief intake and profiling would fail silently "
            "later. A root declared in LOCAL_SOURCE_ROOTS is mounted when the app "
            "assembles, so one added since the API started needs a restart.",
            file=sys.stderr,
        )
        return False


def _fixed_root(root: PackageRoot) -> Callable[[str], PackageRoot]:
    def factory(_: str) -> PackageRoot:
        return root

    return factory


def _declared_by_folder(session: Session, folder_name: str) -> tuple[Generator, str]:
    """Split a generator folder into the lineage it names and the version it declares.

    Two conventions, tried in that order, because the trees they belong to are authored by
    different hands. `<name>@<version>` is the repo's own `courses/` convention (ADR-0027 §5):
    a human types it, and the separator is unambiguous because `@` appears in neither half.
    A generator that writes its own output tree names the folder after itself —
    `learnpack-generator-04a7dd5-dirty` — where the separator is a hyphen the VERSION also
    contains, so the split cannot be made syntactically at all.

    It is made against the registry instead: the registered lineage whose name the folder
    starts with, and whatever follows the separating hyphen is the version. That keeps the
    invariant the first convention had — mechanical intake never mints a generator identity
    (ADR-0024, ADR-0031) — and it is the reason the lineage must be registered first. The
    longest match wins, so a lineage whose name is a prefix of another still resolves.
    """
    generators = SqlAlchemyGeneratorRepository(session)

    name, sep, version = folder_name.rpartition("@")
    if sep and name and version:
        generator = generators.find_by_name_key(normalized_name(name))
        if generator is None:
            raise UnknownGeneratorVersion(
                f"folder '{folder_name}' names no registered generator '{name}' — register it "
                "first (app.cli register-generator)"
            )
        return generator, version

    candidates = [
        (generator, folder_name[len(generator.name) + 1 :])
        for generator in generators.list_all()
        if folder_name.lower().startswith(generator.name.lower() + "-")
    ]
    if not candidates:
        raise UnknownGeneratorVersion(
            f"folder '{folder_name}' is not 'unknown', not '<name>@<version>', and starts "
            "with no registered generator's name — register the generator first "
            "(app.cli register-generator), or rename the folder (see courses/README.md)"
        )
    return max(candidates, key=lambda pair: len(pair[0].name))


def _generator_for_folder(session: Session, folder_name: str) -> UUID | None:
    """Resolve a generator folder to the `GeneratorVersion` its courses declare (ADR-0024).

    `unknown` declares none. Everything else names a lineage, which must already be
    registered, and a version — which is **registered here if it is new**. That asymmetry is
    the decision, not an oversight: a lineage's name is typed once and never again, so a near
    miss mints a second lineage nobody notices (ADR-0031 guards it with `--distinct-from`),
    while a version is a fact about a run that changes with every commit of the generator
    being measured. Demanding a second command for each one would put a manual act inside the
    loop this intake exists to automate.
    """
    if folder_name == "unknown":
        return None

    generator, version = _declared_by_folder(session, folder_name)
    versions = SqlAlchemyGeneratorVersionRepository(session)
    match = next(
        (v for v in versions.list_all() if (v.generator_id, v.version) == (generator.id, version)),
        None,
    )
    if match is not None:
        return match.id

    uow = UnitOfWork(session)
    registered = RegisterGeneratorVersion(
        SqlAlchemyGeneratorRepository(session), versions, uow.events, uow
    )(RegisterGeneratorVersionCommand(generator_id=generator.id, version=version))
    # Printed, never silent: registering a version is an act, and a typo in a folder name is
    # how an individual nobody meant to measure enters the registry.
    print(f"  registered generator version {generator.name} {version} ({registered.id})")
    return registered.id


def _register_package(
    source_locator: str,
    root_factory: Callable[[str], PackageRoot],
    generator_version_id: UUID | None,
    package_format: str,
    edit_provenance: str,
    version: str,
    consumable_url: str | None = None,
) -> tuple[str, str, UUID]:
    """Register one source through the canonical path.

    Returns (status, detail, content id) — the id so the caller can report what the
    auto-profiling policy did with what it just registered (`_report_profiling`).
    """
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        register = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
            # Locators are URLs in both modes (http sources and the dev mount).
            brief_intake=PackageBriefIntake(HttpFetcher()),
        )
        use_case = RegisterPackageFromSource(PackageDiscovery(root_factory), register)
        registration = use_case(
            RegisterPackageFromSourceCommand(
                package_format=package_format,
                source_locator=source_locator,
                generator_version_id=generator_version_id,
                edit_provenance=edit_provenance,
                version=version,
                consumable_url=consumable_url,
            )
        )
    content = registration.content
    if registration.created:
        return (
            "created",
            f"{content.external_id} v{content.version} "
            f"({registration.artifact_count} artifacts, id {content.id})",
            content.id,
        )
    return (
        "unchanged",
        f"{content.external_id} already registered as v{content.version} with identical content",
        content.id,
    )


def _report_profiling(content_ids: list[UUID]) -> None:
    """What the auto-profiling policy did with what was just registered.

    The policy runs inside each registration's own post-commit dispatch (ADR-0003), so by the
    time this prints it has already run or already declined. Both silences need breaking: a
    decline is silent by design (ADR-0029 §3) and a failure is a log line the dispatcher
    swallowed. This is the only place the loop says which of the three happened.

    Counts only what this run CREATED: an unchanged registration emits no event, so its
    profile — if any — is old news, and counting it would report work this run did not do.
    """
    if not content_ids:
        return
    profiled = failed = 0
    with SessionLocal() as session:
        queries = ContentProfilingQueries(session)
        for content_id in content_ids:
            profile = queries.get_profile(content_id)
            if profile is None:
                continue
            profiled += profile.status == "ok"
            failed += profile.status == "failed"
    unprofiled = len(content_ids) - profiled - failed
    print(f"profiling: {profiled} profiled, {failed} failed, {unprofiled} not profiled")
    if profiled == 0 and failed == 0:
        # The two guards that decline in silence, named where someone will read them.
        print(
            "  nothing was auto-profiled: profiling is armed per adapter version by "
            "`accept-extraction --package-format <format>` (ADR-0012), and only reaches "
            "packages whose locators are http(s) URLs (ADR-0029)"
        )


def run_register_package(
    source: str,
    generator: str,
    package_format: str,
    edit_provenance: str,
    version: str,
    consumable_url: str | None,
    root_key: str = BUILTIN_SOURCE_ROOT,
) -> int:
    """One source: an http(s) URL, or a directory inside a declared source root.

    A relative path is read against `--root`, an absolute one against whichever declared root
    holds it — the same answer either way, since a package that no root serves has no honest
    registration available (ADR-0035 §1).
    """
    generator_version_id = None if generator == "unknown" else UUID(generator)
    if generator_version_id is not None:
        with SessionLocal() as session:
            if (
                SqlAlchemyGeneratorVersionRepository(session).get_by_id(generator_version_id)
                is None
            ):
                print(
                    f"generator version {generator_version_id} is not registered",
                    file=sys.stderr,
                )
                return 1

    try:
        if source.startswith(("http://", "https://")):
            root_factory: Callable[[str], PackageRoot] = HttpPackageRoot
        else:
            course_dir = Path(source)
            if not course_dir.is_dir():
                # A path that names nothing from here is read as one relative to the root,
                # which is how the folder reads on screen when you list the tree.
                course_dir = _declared_root(root_key).path / source
            if not course_dir.is_dir():
                print(f"'{source}' is neither an http(s) URL nor a directory", file=sys.stderr)
                return 1
            root = _course_root(course_dir)
            if not _mount_preflight(root, course_dir):
                return 1
            root_factory = _fixed_root(root)
        status, detail, content_id = _register_package(
            source,
            root_factory,
            generator_version_id,
            package_format,
            edit_provenance,
            version,
            consumable_url,
        )
    except DuplicateContent as exc:
        print(f"CONFLICT: {exc}", file=sys.stderr)
        return 1
    except (
        PackageDiscoveryError,
        InvalidContent,
        UnknownGeneratorVersion,
        _UndeclaredRoot,
        local_sources.LocalSourceError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"{status}  {detail}")
    # Single-source registration is what a human runs while debugging one course — exactly
    # when "did it profile?" is the question.
    _report_profiling([content_id] if status == "created" else [])
    return 0


@dataclass(frozen=True)
class TreeRegistration:
    """What registering a tree of generator folders did. `content_ids` carries the courses
    that ended up registered — created now or unchanged from before — because a caller
    composing a study out of them cares which packages are in the store, not which ones this
    run happened to write."""

    created: int
    unchanged: int
    conflicts: int
    invalid: int
    created_ids: list[UUID]
    content_ids: list[UUID]


def _register_tree(
    root_dir: Path, package_format: str, edit_provenance: str, folder: str | None = None
) -> TreeRegistration | None:
    """Register every `<generator-folder>/<course>/` under `root_dir`, or under one folder of
    it. `None` means nothing was written: the tree was refused whole.

    Batch is a loop over the same use case, not another path (ADR-0027).
    """
    if not root_dir.is_dir():
        print(
            f"'{root_dir.as_posix()}' does not exist — a tree holds "
            "<generator-folder>/<course>/ (see courses/README.md)",
            file=sys.stderr,
        )
        return None

    if folder is not None:
        generator_dirs = [root_dir / folder] if (root_dir / folder).is_dir() else []
        if not generator_dirs:
            print(f"'{folder}' is not a folder of {root_dir.as_posix()}", file=sys.stderr)
            return None
    else:
        generator_dirs = sorted(d for d in root_dir.iterdir() if d.is_dir())

    course_dirs = [
        (parent, course)
        for parent in generator_dirs
        for course in sorted(d for d in parent.iterdir() if d.is_dir())
    ]
    if not course_dirs:
        print(f"no courses found under {root_dir.as_posix()}")
        return TreeRegistration(0, 0, 0, 0, [], [])

    # A tree-wide declaration deserves a tree-wide check (the ADR-0024 pattern): every
    # generator folder resolves before anything registers, so a typo is one clean abort.
    generators_by_folder: dict[str, UUID | None] = {}
    problems: list[str] = []
    with SessionLocal() as session:
        for parent in generator_dirs:
            try:
                generators_by_folder[parent.name] = _generator_for_folder(session, parent.name)
            except UnknownGeneratorVersion as exc:
                problems.append(str(exc))
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("nothing was registered", file=sys.stderr)
        return None

    if not _mount_preflight(_course_root(course_dirs[0][1]), course_dirs[0][1]):
        return None

    created_ids: list[UUID] = []
    content_ids: list[UUID] = []
    created = unchanged = conflicts = invalid = 0
    for parent, course_dir in course_dirs:
        label = f"{parent.name}/{course_dir.name}"
        try:
            root = _course_root(course_dir)
            status, detail, content_id = _register_package(
                str(course_dir),
                _fixed_root(root),
                generators_by_folder[parent.name],
                package_format,
                edit_provenance,
                DEFAULT_VERSION,
            )
        except DuplicateContent as exc:
            conflicts += 1
            print(f"  CONFLICT  {label}: {exc}", file=sys.stderr)
            continue
        except (PackageDiscoveryError, InvalidContent, UnknownGeneratorVersion) as exc:
            invalid += 1
            print(f"  INVALID  {label}: {exc}", file=sys.stderr)
            continue
        created += status == "created"
        unchanged += status == "unchanged"
        content_ids.append(content_id)
        if status == "created":
            created_ids.append(content_id)
        print(f"  {status}  {detail}")

    print(f"\n{created} created, {unchanged} unchanged, {conflicts} conflicts, {invalid} invalid")
    _report_profiling(created_ids)
    return TreeRegistration(created, unchanged, conflicts, invalid, created_ids, content_ids)


def run_register_package_all(courses_dir: Path, package_format: str, edit_provenance: str) -> int:
    result = _register_tree(courses_dir, package_format, edit_provenance)
    if result is None:
        return 1
    # A failed profile is not a failed registration: the evaluand is registered either way
    # (the hard/soft split of ADR-0027 §3). The exit code stays about registration.
    return 1 if result.conflicts or result.invalid else 0


# --------------------------------------------------------------------------- studies
# The manual loop (13-code §3.6): declare → pin → compose → open → publish → show-report,
# with `show-preview` readable at any point along it — publishing is irreversible, and
# reading what it would write is not.
# Studies never command Orchestration — the wiring between rounds is this actor's.

_STUDY_ERRORS = (
    StudyNotFound,
    InvalidStudy,
    InstrumentNotChosen,
    InstrumentNotPublished,
    AssessorNotChosen,
    AssessorHasNotRatified,
    InstrumentRequiredFirst,
    UnknownInstrument,
    UnknownBrief,
    ScopeNamesUnknownGenerator,
    GeneratorScopeNotDeclared,
    DatasetLocked,
    DatasetEmpty,
    StudyAlreadyOpen,
    StudyNotOpen,
    StudyAlreadySignedOff,
)


CLEAR_ASSESSOR = "none"


class _AssessorNotRegistered(Exception):
    """`--assessor` named something no `ratify-assessor` has ever created."""


def _selected_assessor(assessor_arg: str | None) -> object:
    """`--assessor` as the selection understands it: absent, cleared, or an id.

    `name:version` here and an id over HTTP, and the difference is deliberate: the console
    picks from a list that already carries ids, while a person at a terminal knows the
    artifact by the name every other command takes. Resolving one into the other is a
    composition root's job, which is what this file is.
    """
    if assessor_arg is None:
        return UNCHANGED
    if assessor_arg == CLEAR_ASSESSOR:
        return None
    package = _assessor_from_spec(assessor_arg)
    if package is None:
        raise _AssessorNotRegistered(f"{assessor_arg} is not a name:version spec")
    with SessionLocal() as session:
        row = SqlAlchemyAssessorRepository(session).get_automated(package.name, package.version)
    if row is None:
        raise _AssessorNotRegistered(
            f"{package.display_name} is not registered — run ratify-assessor first"
        )
    return row.id


class _ContradictoryScope(Exception):
    """Both forms of the scope at once — which one the caller meant is not ours to guess."""


def _scope(generator_version_ids: list[UUID] | None, all_generators: bool) -> SelectedScope:
    """The two flags, collapsed into the one value the domain holds (ADR-0044 §1).

    Passing neither leaves the scope alone, which is what every other flag of this command
    does — the demand for a declaration belongs to `open-study`, so a draft can still be
    built up one call at a time."""
    if all_generators and generator_version_ids:
        raise _ContradictoryScope(
            "--all-generator-versions and --generator-version-id say different things; "
            "pass one of them"
        )
    if all_generators:
        return ALL_GENERATORS
    if generator_version_ids:
        return tuple(generator_version_ids)
    return UNCHANGED


def _selection(
    instrument_version_id: str | None,
    assessor_arg: str | None,
    brief_ids: list[UUID] | None,
    generator_version_ids: list[UUID] | None = None,
    all_generators: bool = False,
) -> StudySelection:
    return StudySelection(
        instrument_version_id=(
            instrument_version_id if instrument_version_id is not None else UNCHANGED
        ),
        assessor_id=_selected_assessor(assessor_arg),  # type: ignore[arg-type]
        brief_ids=brief_ids if brief_ids is not None else UNCHANGED,
        generator_scope=_scope(generator_version_ids, all_generators),
    )


def _scope_label(study: Study) -> str:
    if study.generator_scope is None:
        return "no generator scope"
    if isinstance(study.generator_scope, tuple):
        return f"{len(study.generator_scope)} versions"
    return "all versions"


def _describe(study: Study) -> str:
    return (
        f"study {study.id} ({study.status}): "
        f"{study.instrument_version_id or 'no instrument'} - "
        f"{study.assessor_id or 'no judge'} - "
        f"{len(study.brief_ids)} briefs x {_scope_label(study)} "
        f"-> {len(study.content_ids)} contents"
    )


def run_declare_study(
    name: str,
    description: str | None,
    instrument_version_id: str | None = None,
    assessor_arg: str | None = None,
    brief_ids: list[UUID] | None = None,
    generator_version_ids: list[UUID] | None = None,
    all_generators: bool = False,
) -> int:
    """Declare a study, with as much of its selection as you already know.

    All of it is optional and all of it stays changeable until `open-study` pins it, so
    creating a complete study in one call and correcting it later run the same checks.

    The generator scope is the one part `open-study` will not do without (ADR-0044 §2):
    either `--all-generator-versions` or one `--generator-version-id` per version the round
    measures.
    """
    try:
        selection = _selection(
            instrument_version_id, assessor_arg, brief_ids, generator_version_ids, all_generators
        )
    except (_AssessorNotRegistered, _ContradictoryScope) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        try:
            study = DeclareStudy(
                studies=SqlAlchemyStudyRepository(session),
                registry=StudiesRegistryGateway(session),
                design=StudiesDesignGateway(session),
                evaluation=StudiesEvaluationGateway(session),
                publisher=uow.events,
                uow=uow,
            )(DeclareStudyCommand(name=name, description=description, selection=selection))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"declared {_describe(study)}")
    return 0


def run_update_study(
    study_id: UUID,
    instrument_version_id: str | None,
    assessor_arg: str | None,
    brief_ids: list[UUID] | None,
    generator_version_ids: list[UUID] | None = None,
    all_generators: bool = False,
) -> int:
    """Change a draft: the norm, the judge, the recipe, or any combination of them.

    One command where three pins used to be, because a draft is one thing being set up and
    none of it is binding until `open-study` (ADR-0043 §1). A flag that is not passed is
    left alone; `--assessor none` is how you drop a judge, which re-pointing a study at a
    version that judge never ratified requires.
    """
    try:
        selection = _selection(
            instrument_version_id, assessor_arg, brief_ids, generator_version_ids, all_generators
        )
    except (_AssessorNotRegistered, _ContradictoryScope) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = UpdateStudyDraft(
            studies=SqlAlchemyStudyRepository(session),
            registry=StudiesRegistryGateway(session),
            design=StudiesDesignGateway(session),
            evaluation=StudiesEvaluationGateway(session),
            uow=uow,
        )
        try:
            study = use_case(UpdateStudyDraftCommand(study_id=study_id, selection=selection))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(_describe(study))
    return 0


def run_open_study(study_id: UUID) -> int:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = OpenStudy(
            studies=SqlAlchemyStudyRepository(session), publisher=uow.events, uow=uow
        )
        try:
            study = use_case(OpenStudyCommand(study_id=study_id))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"opened study {study.id}: dataset fixed at {len(study.content_ids)} contents")
    return 0


def run_sign_off_study(study_id: UUID, email: str) -> int:
    """The human act: compose the report from the current judgments, freeze it and sign it."""
    with SessionLocal() as session:
        assessor = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if assessor is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1
        uow = UnitOfWork(session)
        use_case = SignOffStudy(
            studies=SqlAlchemyStudyRepository(session),
            reports=SqlAlchemyStudyReportRepository(session),
            registry=StudiesRegistryGateway(session),
            evaluation=StudiesEvaluationGateway(session),
            design=StudiesDesignGateway(session),
            profiling=StudiesProfilingGateway(session),
            publisher=uow.events,
            uow=uow,
        )
        try:
            study = use_case(SignOffStudyCommand(study_id=study_id, signed_off_by=assessor.id))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"signed off study {study.id} (by {email}) — the report is now immutable")
    return 0


def run_show_report(study_id: UUID) -> int:
    with SessionLocal() as session:
        dto = SqlAlchemyStudyReportRepository(session).get(study_id)
    if dto is None:
        print(f"study {study_id} has no signed-off report", file=sys.stderr)
        return 1
    print(json.dumps(dto.report, indent=2))
    return 0


def run_show_preview(study_id: UUID) -> int:
    """What signing off WOULD write, composed on demand — the report before the act.

    A command of its own rather than a flag on `show-report`: that one prints the frozen
    row and says so when there is none, and a flag that silently changes which of two
    documents you got is the confusion this document's own `documentKind` marker fights.
    """
    with SessionLocal() as session:
        study = SqlAlchemyStudyRepository(session).get_by_id(study_id)
        if study is None:
            print(f"study {study_id} not found", file=sys.stderr)
            return 1
        inputs = gather_report_inputs(
            study,
            StudiesRegistryGateway(session),
            StudiesEvaluationGateway(session),
            StudiesDesignGateway(session),
            StudiesProfilingGateway(session),
        )
        preview = compose_preview(
            study=study,
            contents=inputs.contents,
            briefs=inputs.briefs,
            generators=inputs.generators,
            judgments=inputs.judgments,
            findings=inputs.findings,
            capabilities=inputs.capabilities,
            instrument=inputs.instrument,
            composed_at=datetime.now(UTC),
        )
    print(json.dumps(preview, indent=2))
    return 0


def run_show_fitness(study_id: UUID) -> int:
    """The fitness projection over a study (ADR-0023) — the GA's read, composed on demand.

    Deliberately not part of `show-report`: an optimization signal is not a judgment, and
    the two use different denominators.
    """
    with SessionLocal() as session:
        study = SqlAlchemyStudyRepository(session).get_by_id(study_id)
        if study is None:
            print(f"study {study_id} not found", file=sys.stderr)
            return 1
        instrument_version_id = study.instrument_version_id
        registry = StudiesRegistryGateway(session)
        contents = registry.get_contents_by_ids(list(study.content_ids))
        # The recipe as well as what the contents reference (ADR-0039 §3): a commission that
        # produced no course is a reading, not an absence.
        briefs = {
            brief_id: brief
            for brief_id in set(study.brief_ids)
            | {c.brief_id for c in contents if c.brief_id is not None}
            if (brief := registry.get_brief(brief_id)) is not None
        }
        generators = {
            content.generator_version_id: generator
            for content in contents
            if content.generator_version_id
            and (generator := registry.get_generator(content.generator_version_id))
        }
        evaluation = StudiesEvaluationGateway(session)
        content_ids = [content.content_id for content in contents]
        projection = compute_fitness(
            study=study,
            instrument=(
                StudiesDesignGateway(session).get_instrument(instrument_version_id)
                if instrument_version_id
                else None
            ),
            contents=contents,
            briefs=briefs,
            generators=generators,
            judgments=(
                evaluation.get_judgments(content_ids, instrument_version_id, study.assessor_id)
                if instrument_version_id
                else []
            ),
            outcomes=(
                evaluation.get_criterion_outcomes(
                    content_ids, instrument_version_id, study.assessor_id
                )
                if instrument_version_id
                else []
            ),
            ratifications=(
                evaluation.list_ratifications(instrument_version_id)
                if instrument_version_id
                else []
            ),
            computed_at=datetime.now(UTC),
        )
    print(json.dumps(projection, indent=2))
    return 0


def run_evaluate_study(
    study_id: UUID, assessor_spec: str | None, concurrency: int | None, re_evaluate: bool
) -> int:
    """Evaluate every course of an open study, in one bounded run.

    Progress goes to stderr and the summary to stdout, the same split `evaluate --dry-run`
    uses: what a script reads is one JSON document, and a batch of twenty courses would
    otherwise bury it in progress lines. Ctrl-C cancels — the same token the console will
    use — and the summary still prints, because half a batch is a result too.
    """
    # Optional now: the study pins its assessor (ADR-0042 §10). Passing one still works and
    # is checked against the pin, so a GA script written before the pin keeps running and a
    # disagreement is refused rather than quietly resolved.
    package = None
    if assessor_spec is not None:
        package = _assessor_from_spec(assessor_spec)
        if package is None:
            return 1

    workers = concurrency if concurrency is not None else get_settings().llm_max_concurrency
    try:
        run = batch_runs.prepare(
            study_id=study_id, package=package, workers=workers, re_evaluate=re_evaluate
        )
    except batch_runs.BatchRefused as exc:
        # Refused before a single call was paid for: every course would have failed the
        # same way, so the message names the act that fixes it.
        print(f"{exc} [{exc.kind}]", file=sys.stderr)
        return 1

    trace = observability.trace_path(f"batch-{run.run_id}")
    sinks = [_print_call]
    if trace is not None:
        sinks.append(observability.jsonl_sink(trace))
    run.sink = observability.fan_out(*sinks)

    print(
        f"evaluating {len(run.pending)} of {len(run.courses)} courses with "
        f"{run.package.display_name} against {run.instrument_version_id}, "
        f"{workers} at a time (study {study_id})",
        file=sys.stderr,
    )
    if len(run.pending) < len(run.courses):
        print(
            f"  {len(run.courses) - len(run.pending)} already evaluated by this assessor — "
            "pass --re-evaluate to do them again",
            file=sys.stderr,
        )

    # Ctrl-C stops the run instead of killing the process mid-course: the workers finish
    # what they are already asking, nothing new starts, and the summary is still printed.
    previous_handler = signal.signal(signal.SIGINT, lambda *_: _cancel_batch(run))
    try:
        batch_runs.execute(run)
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    view = run.view()
    for outcome in view.outcomes:
        detail = f" ({outcome.cause})" if outcome.cause else ""
        print(f"  {outcome.status:10} {outcome.external_id}{detail}", file=sys.stderr)
    if trace is not None and trace.exists():
        print(f"LLM trace: {trace}", file=sys.stderr)

    print(json.dumps(_batch_summary(view), indent=2))
    # A batch that ended for a reason is a failed command, even though what succeeded stays
    # persisted: a script must not read "cancelled" or "refused" as a finished generation.
    return 0 if view.status == "done" and view.failed == 0 else 1


def _cancel_batch(run: batch_runs.BatchRun) -> None:
    print(
        "\ncancelling: no further courses will start, and the ones in flight stop at their "
        "next call. What already finished is persisted.",
        file=sys.stderr,
    )
    run.cancel()


def _batch_summary(view: batch_runs.BatchView) -> dict[str, Any]:
    """What a script reads to know how a generation went, per course and in total."""
    return {
        "runId": str(view.run_id),
        "studyId": str(view.study_id),
        "instrumentVersionId": view.instrument_version_id,
        "assessor": {"name": view.package.name, "version": view.package.version},
        "status": view.status,
        "startedAt": view.started_at.isoformat(),
        "elapsedMs": view.elapsed_ms,
        "totals": {
            "courses": view.total,
            "evaluated": view.evaluated,
            "skipped": view.skipped,
            "failed": view.failed,
            "cancelled": sum(1 for o in view.outcomes if o.status == "cancelled"),
            "llmCalls": sum(o.llm_calls for o in view.outcomes),
        },
        "error": view.error,
        "courses": [
            {
                "contentId": str(outcome.content_id),
                "externalId": outcome.external_id,
                # The grouping axis of the fitness (ADR-0039), so a generation's courses can
                # be read by commission without a second query.
                "briefId": str(outcome.brief_id) if outcome.brief_id else None,
                "status": outcome.status,
                "cause": outcome.cause,
                "durationMs": outcome.duration_ms,
                "llmCalls": outcome.llm_calls,
                "evaluationId": (
                    str(outcome.evaluation_id) if outcome.evaluation_id is not None else None
                ),
            }
            for outcome in view.outcomes
        ],
    }


# --------------------------------------------------------------------------- seed-workbench
# The acts that make a fresh local database able to MEASURE something, applied from a
# manifest (ADR-0045). Each one is a human act elsewhere — publishing an instrument
# (ADR-0012), accepting an extraction (ADR-0012), ratifying an assessor (ADR-0019) — and each
# one is replayed here, under the local-mode gate, over artifacts the team already reviewed.
# It decides nothing: what is published is what the manifest names.

WORKBENCH_MANIFEST = REPO_ROOT / "docs" / "seed" / "workbench.yaml"

# The identity every replayed act is attributed to. It is the same admin `seed-demo` creates,
# because there is only one local admin and two of them would be two histories.
WORKBENCH_ADMIN = ("admin@local.dev", "Admin")


def _ensure_local_assessor(session: Session, email: str, display_name: str, role: Role) -> UUID:
    """Create a local identity, or align the role of one that already exists.

    Aligning matters: signing in as `admin@local.dev` before seeding creates that assessor as
    an `evaluator` (ResolveAssessor's default). Leaving it would print "admin" for someone who
    then gets 403 everywhere. This is a seeder, not a login path — the ADR-0007 invariant it
    must not break is that *logging in* never changes a role.
    """
    repository = SqlAlchemyAssessorRepository(session)
    assessor = repository.get_by_email(email)
    if assessor is None:
        assessor = Assessor(
            id=new_id(),
            # Must match what auth_local derives from `X-Dev-User`, or the sign-in would
            # create a second assessor for the same person.
            clerk_user_id=f"local|{email.lower()}",
            email=email,
            display_name=display_name,
            role=role,
        )
        repository.add(assessor)
        session.commit()
    elif assessor.role is not role:
        previous = assessor.role
        assessor.assign_role(role)
        repository.update(assessor)
        session.commit()
        print(f"  {email}: role {previous} -> {role.value}")
    return assessor.id


def _instrument_identity(spec_file: Path) -> tuple[str, str]:
    """The lineage and the version id an authored YAML will have once imported. Read off the
    file rather than declared in the manifest: two places to write `course-drafts-qa-v6` is
    one place to get it wrong, and the importer mints the id from exactly these two fields."""
    spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    return spec["instrument_id"], f"{spec['instrument_id']}-{spec['version']}"


def _publish_workbench_instrument(spec_file: Path, admin_email: str) -> str | None:
    """Import the authored YAML and publish it, or leave a published version alone.

    A published version is immutable (ADR-0012), so re-importing over one is refused — which
    is exactly what makes this the idempotent branch rather than an error to swallow: if the
    version is already published, the file on disk and the row already agree, and there is
    nothing to do.
    """
    _, version_id = _instrument_identity(spec_file)
    with SessionLocal() as session:
        existing = SqlAlchemyInstrumentRepository(session).get(version_id)
    if existing is not None and existing.is_published:
        print(f"instrument {version_id} is already published")
        return version_id

    if run_import_instrument(spec_file) != 0:
        return None
    if run_publish_instrument(version_id, admin_email) != 0:
        return None
    return version_id


def run_seed_workbench(manifest_file: Path = WORKBENCH_MANIFEST) -> int:
    """Leave a local database able to measure: instruments published, extractions accepted,
    assessors ratified, generator lineages registered. Idempotent — run it as often as you
    like, and after every `alembic upgrade head` that reset the store."""
    if not _local_mode_only("seed-workbench"):
        return 1

    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    admin_email, admin_name = WORKBENCH_ADMIN

    with SessionLocal() as session:
        _ensure_local_assessor(session, admin_email, admin_name, Role.ADMIN)

    published: dict[str, str] = {}
    for relative in manifest.get("instruments", []):
        spec_file = manifest_file.parent / relative
        lineage, _ = _instrument_identity(spec_file)
        if lineage in published:
            print(
                f"the manifest publishes two versions of '{lineage}' — which one an assessor "
                "should be ratified against is not this command's to guess",
                file=sys.stderr,
            )
            return 1
        version_id = _publish_workbench_instrument(spec_file, admin_email)
        if version_id is None:
            return 1
        published[lineage] = version_id

    for package_format in manifest.get("extractions", []):
        if run_accept_extraction(package_format, admin_email) != 0:
            return 1

    # Registering the lineage is guarded against a near miss (ADR-0031) and refuses a
    # duplicate, so what makes this idempotent is asking first rather than swallowing the
    # refusal — a swallowed one would also hide the guard firing on a real typo.
    for name in manifest.get("generators", []):
        with SessionLocal() as session:
            known = SqlAlchemyGeneratorRepository(session).find_by_name_key(normalized_name(name))
        if known is not None:
            print(f"generator {known.name} is already registered ({known.id})")
        elif run_register_generator(name, distinct_from=None) != 0:
            return 1

    # Which assessors exist is the code registry's answer (ADR-0016), not the manifest's:
    # adding a package is adding an assessor, and it should not also need an edit here to be
    # usable. What the manifest decides is which VERSION of its lineage each one judges.
    ratified = 0
    for package in AUTOMATED_ASSESSORS.values():
        version_id = published.get(package.instrument_id)
        if version_id is None:
            print(
                f"{package.display_name}: no published version of '{package.instrument_id}' "
                "in the manifest — not ratified"
            )
            continue
        if run_ratify_assessor(package.name, package.version, version_id, admin_email, []) != 0:
            return 1
        ratified += 1

    print(
        f"\nworkbench ready: {len(published)} instrument(s) published, "
        f"{len(manifest.get('extractions', []))} extraction(s) accepted, "
        f"{ratified} assessor(s) ratified\n"
    )
    print(f"  sign in at http://localhost:3000 as {admin_email}")
    print("  register a generation with `register-package --all --root <key>`")
    return 0


# --------------------------------------------------------------------------- seed-demo
# A ready-to-use local dataset (ADR-0008), for contributors who work on rubrics, metrics and
# evaluations and should not need a Clerk account or a Neon database to run the app.
#
# It goes through the real use cases instead of raw INSERTs, so the events are published and
# the policies run exactly as they would in production.

DEMO_INSTRUMENT_VERSION_ID = "learnpack-pedagogical-v1"
DEMO_REQUIRED_EVALUATIONS = 2  # two raters per content: the minimum that yields inter-rater

# (email, display name, role). `clerk_user_id` mirrors what auth_local builds from the header,
# and the display names are exactly what `display_name_for` derives from these emails — so
# signing in refreshes the profile to the same value instead of silently renaming people.
DEMO_ASSESSORS: list[tuple[str, str, Role]] = [
    ("admin@local.dev", "Admin", Role.ADMIN),
    ("ada.lovelace@local.dev", "Ada Lovelace", Role.EVALUATOR),
    ("grace.hopper@local.dev", "Grace Hopper", Role.EVALUATOR),
]

# No metadata on purpose: these generated packages declare no objectives, audience or
# prerequisites, and hand-writing them here (from the brief material, or worse, derived
# with AI) would contaminate the declared surface the instrument evaluates — the profiles
# must read `absent`, which is the true finding about this generator. That input-side
# information belongs to the GenerationBrief (pending intake — see STATUS).
#
# The URLs below are *declarations* of a real deployment (ADR-0028), not overrides of
# something discovery found: `_demo_root` prefixes locators with the course slug, which is no
# URL at all. They are why the demo keeps a working iframe while local courses do not.
DEMO_CONTENTS: list[dict[str, Any]] = [
    {
        "package_format": "LearnpackV1",
        "external_id": "introduction-to-generative-ai",
        "version": "1",
        "consumable_url": "https://introduction-to-generative-ai.learn-pack.com/",
        # Declared, not defaulted (ADR-0024). The seeder links this one to the demo
        # generator and leaves the other unknown, so both paths are visible locally.
        "generator_version_id": "demo",
    },
    {
        "package_format": "LearnpackV1",
        "external_id": "object-representation-in-python",
        "version": "1",
        "consumable_url": "https://object-representation-in-python.learn-pack.com/",
        "generator_version_id": None,
    },
]


def _local_mode_only(command: str) -> bool:
    """The guard that keeps a seeder out of a real store.

    A seeder writes wherever DATABASE_URL points, so it refuses to run unless the process is
    configured for local development. For `seed-workbench` the stake is larger than stray
    rows: it replays acts that are human ones by decision (ADR-0045), and outside a dev box
    the person who publishes an instrument or ratifies an assessor is a person.
    """
    if get_settings().is_local_auth:
        return True
    print(
        f"{command} only runs with AUTH_MODE=local: it writes on behalf of the local admin, "
        "which must never happen in a real database.",
        file=sys.stderr,
    )
    return False


def _seed_demo_assessors(session: Session) -> dict[str, UUID]:
    """Create the demo users, and align the role of any that already exist."""
    return {
        email: _ensure_local_assessor(session, email, display_name, role)
        for email, display_name, role in DEMO_ASSESSORS
    }


# The demo courses ARE the frozen real packages of the adapter's fixture suite — same two
# courses, same files — so the local workbench shows a full extraction, not a stub.
# Local-only by construction: seed-demo requires AUTH_MODE=local (ADR-0008).
DEMO_PACKAGES_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "learnpack_v1"


def _demo_root(course_slug: str) -> FilesystemPackageRoot:
    """The frozen package's root: locators stay `<slug>/…`, relative to DEMO_PACKAGES_DIR,
    resolved at profiling time by the filesystem fetcher — exactly what the hand-rolled
    artifact list produced before discovery took over (ADR-0027)."""
    return FilesystemPackageRoot(DEMO_PACKAGES_DIR / course_slug, locator_base=course_slug)


DEMO_GENERATOR = ("learnpack-generator", "1.0.0")


def _seed_demo_generator() -> UUID:
    """The demo's declared examinee, seeded as the two acts it now is (ADR-0031): the lineage,
    then a version under it. One course is linked to that version and the other is declared
    unknown (ADR-0024), so the local study report exercises both paths: a populated generator
    level and the `unknownExclusions` caveat.

    Returns the **version** id, which is what a content declares."""
    name, version = DEMO_GENERATOR
    with SessionLocal() as session:
        generators = SqlAlchemyGeneratorRepository(session)
        versions = SqlAlchemyGeneratorVersionRepository(session)

        generator = generators.find_by_name_key(normalized_name(name))
        if generator is None:
            uow = UnitOfWork(session)
            generator = RegisterGenerator(generators, uow.events, uow)(
                RegisterGeneratorCommand(name=name)
            )

        declared = (generator.id, version)
        existing = next(
            (v for v in versions.list_all() if (v.generator_id, v.version) == declared), None
        )
        if existing is not None:
            return existing.id

        uow = UnitOfWork(session)
        registered = RegisterGeneratorVersion(generators, versions, uow.events, uow)(
            RegisterGeneratorVersionCommand(
                generator_id=generator.id,
                version=version,
                # Optional reference prose, the only key the console writes (ADR-0030 §2).
                metadata={"changelog": "First registered version of the demo generator."},
            )
        )
        return registered.id


def _seed_demo_contents(generator_id: UUID) -> dict[str, UUID]:
    """Register the demo courses through the discovery intake (ADR-0027); reuse them if
    already there — by content hash when the row has one, by declared identity otherwise
    (rows seeded before the hash existed)."""
    ids: dict[str, UUID] = {}

    for raw in DEMO_CONTENTS:
        slug = raw["external_id"]
        declared = generator_id if raw["generator_version_id"] == "demo" else None
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            register = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
                brief_intake=PackageBriefIntake(FilesystemFetcher(DEMO_PACKAGES_DIR)),
            )
            use_case = RegisterPackageFromSource(PackageDiscovery(_demo_root), register)
            try:
                registration = use_case(
                    RegisterPackageFromSourceCommand(
                        package_format=raw["package_format"],
                        source_locator=slug,
                        generator_version_id=declared,
                        version=raw["version"],
                        consumable_url=raw["consumable_url"],
                    )
                )
                ids[slug] = registration.content.id
            except DuplicateContent:
                snapshot = next(
                    s
                    for s in EvaluandRegistryQueries(session).list_content_snapshots()
                    if s.package_format == raw["package_format"]
                    and s.external_id == slug
                    and s.version == raw["version"]
                )
                ids[slug] = snapshot.content_id

    return ids


def _seed_demo_campaign(content_ids: list[UUID]) -> UUID:
    """One open campaign over the demo courses. Reuses the existing one if it is still open."""
    wanted = set(content_ids)

    with SessionLocal() as session:
        campaigns = SqlAlchemyCampaignRepository(session)
        for campaign in campaigns.list_all():
            if (
                campaign.status == "open"
                and campaign.instrument_version_id == DEMO_INSTRUMENT_VERSION_ID
                and wanted.issubset(set(campaign.content_ids))
            ):
                return campaign.id

        uow = UnitOfWork(session)
        campaign = OpenCampaign(campaigns, uow.events, uow)(
            OpenCampaignCommand(
                instrument_version_id=DEMO_INSTRUMENT_VERSION_ID,
                required_evaluations_per_content=DEMO_REQUIRED_EVALUATIONS,
                content_ids=content_ids,
            )
        )
        return campaign.id


def _seed_demo_assignments(
    campaign_id: UUID, content_ids: list[UUID], evaluator_ids: list[UUID]
) -> int:
    """Every evaluator gets every course. Nothing is evaluated: the demo starts pending."""
    created = 0

    for assessor_id in evaluator_ids:
        for content_id in content_ids:
            with SessionLocal() as session:
                uow = UnitOfWork(session)
                assign = AssignContent(
                    campaigns=SqlAlchemyCampaignRepository(session),
                    assignments=SqlAlchemyAssignmentRepository(session),
                    publisher=uow.events,
                    uow=uow,
                )
                try:
                    assign(
                        AssignContentCommand(
                            campaign_id=campaign_id,
                            content_id=content_id,
                            assessor_id=assessor_id,
                        )
                    )
                    created += 1
                except DuplicateAssignment:
                    pass

    return created


def _reset_demo(session: Session) -> None:
    """Wipe the local dataset: everything the app writes, minus the seeded reference data.

    Deliberately wholesale rather than "delete what DEMO_ASSESSORS/DEMO_CONTENTS list today".
    Editing those lists is the normal way to shape a demo, and a scoped delete strands every
    row the previous version created: a renamed user keeps showing up in the sign-in picker, a
    replaced course lingers with no campaign, and no reset can ever reach them.

    Safe because it can only ever run against a local database: `run_seed_demo` requires
    AUTH_MODE=local, and `Settings` refuses that mode unless DATABASE_URL is local (ADR-0008).
    Assessors are still scoped to `local|`, the identities this mode creates — a real Clerk
    identity is never touched.
    """
    for statement in (
        "DELETE FROM studies",  # recipe/dataset/report cascade; before contents (stale refs)
        "DELETE FROM criterion_scores",
        "DELETE FROM evaluations",
        "DELETE FROM content_evaluation_completions",
        "DELETE FROM golden_references",
        "DELETE FROM assignments",
        "DELETE FROM campaign_contents",
        "DELETE FROM campaigns",
        "DELETE FROM content_profiles",  # entries/extras cascade; before contents (FK)
        "DELETE FROM extraction_acceptances",
        # App-minted (instrument import), not seeded reference data — wiped so the demo
        # re-import can recreate the draft without tripping the ADR-0014 lint or, if the
        # local version was published while testing, the immutability rule (locally,
        # instrument versions are disposable — the experimental-phase convention).
        "DELETE FROM instrument_versions",  # claims/criteria/ratifications cascade
        "DELETE FROM data_requirements",
        "DELETE FROM contents",
        # Intake-derived (ADR-0022), not seeded reference data; after contents (FK).
        "DELETE FROM generation_briefs",
        # Registered by the seeder (ADR-0024), not seeded reference data; after contents.
        "DELETE FROM generator_versions",
        # The lineage owns the versions (ADR-0031); after them (FK).
        "DELETE FROM generators",
        "DELETE FROM events",
        # Ratifications reference assessors on both sides (ADR-0019); before assessors.
        "DELETE FROM assessor_ratifications",
        # Automated assessors are app-minted too — registered at their first ratification,
        # never seeded. Leaving one behind strands its stored `source_config`, and the next
        # ratification refuses with "the artifact changed without a version bump"
        # (ADR-0016): a correct guard, firing on a database the operator was told had been
        # reset. They carry no clerk_user_id, so the human predicate below never reaches
        # them.
        "DELETE FROM assessors WHERE kind = 'automated'",
        "DELETE FROM assessors WHERE clerk_user_id LIKE 'local|%'",
    ):
        session.execute(text(statement))
    session.commit()


DEMO_INSTRUMENT_SPEC = REPO_ROOT / "docs" / "seed" / "instruments" / "learnpack-course-qa-v1.yaml"


def _seed_demo_acceptance(admin_id: UUID) -> None:
    """Accept the current LearnpackV1 adapter (demo only — in the real store this is the
    team's deliberate act, ADR-0012).

    It arms the automatic policy for anything registered from an http source afterwards. It
    is NOT what profiles the demo courses: their locators are relative to the frozen fixture
    tree, so the policy declines them (ADR-0029 §2) and `_seed_demo_profiles` does the work.
    """
    adapter = ADAPTERS_BY_FORMAT["LearnpackV1"]
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        AcceptExtraction(
            acceptances=SqlAlchemyAcceptanceRepository(session), publisher=uow.events, uow=uow
        )(
            AcceptExtractionCommand(
                package_format="LearnpackV1",
                adapter_version=adapter.adapter_version,
                accepted_by=admin_id,
            )
        )


def _seed_demo_profiles(content_ids: dict[str, UUID]) -> int:
    """Profile the demo courses. The automatic policy never reaches them — `_demo_root`
    prefixes locators with the bare course slug, and the policy fetches over http only
    (ADR-0029 §2) — so this step is not redundant, and it stays necessary even for a reused
    content, which emits no event at all.

    Artifacts are the frozen real packages, so the workbench shows the full extraction:
    lesson inventory, verbatim bodies and activity counts, plus the declared metadata.
    """
    profiled = 0
    for content_id in content_ids.values():
        with SessionLocal() as session:
            use_case = _build_profile_content(session, base_dir=DEMO_PACKAGES_DIR)
            try:
                use_case(ProfileContentCommand(content_id=content_id))
                profiled += 1
            except ProfileAlreadyExists:
                pass
    return profiled


def run_seed_demo(reset: bool) -> int:
    """Users + courses + profiles + an open campaign + assignments, all pending. Idempotent."""
    if not _local_mode_only("seed-demo"):
        return 1

    with SessionLocal() as session:
        if reset:
            _reset_demo(session)
            print("wiped the local dataset (courses, campaigns, evaluations, local users)")
        assessor_ids = _seed_demo_assessors(session)

    # The instrument draft mints the data_requirements the extraction conforms to
    # (ADR-0014). It stays a DRAFT: publishing is the team's act, never the seeder's.
    if run_import_instrument(DEMO_INSTRUMENT_SPEC) != 0:
        return 1
    _seed_demo_acceptance(assessor_ids["admin@local.dev"])

    generator_id = _seed_demo_generator()
    # The automatic policy declines these: their locators are relative to the frozen fixture
    # tree, and it fetches over http only (ADR-0029 §2). Hence the explicit step below.
    content_ids = _seed_demo_contents(generator_id)
    profiled = _seed_demo_profiles(content_ids)
    campaign_id = _seed_demo_campaign(list(content_ids.values()))
    evaluator_ids = [
        assessor_ids[email] for email, _, role in DEMO_ASSESSORS if role is Role.EVALUATOR
    ]
    created = _seed_demo_assignments(campaign_id, list(content_ids.values()), evaluator_ids)

    print(
        f"\ndemo ready: {len(content_ids)} courses ({profiled} newly profiled), "
        f"1 open campaign (quorum {DEMO_REQUIRED_EVALUATIONS}), {created} new assignments\n"
    )
    for email, display_name, role in DEMO_ASSESSORS:
        print(f"  {role.value:<9} {email:<24} {display_name}")
    print("\nsign in at http://localhost:3000 - start with admin@local.dev")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Logging first: the dispatcher swallows a failing policy into `logger.exception`, and
    # with no configured root logger that traceback never reaches the console — the message
    # arrives via logging's lastResort, the stack does not. stderr because results go to
    # stdout and some of them are piped; ASCII-only format because a Windows cp1252 console
    # raises UnicodeEncodeError on anything else (see main.py). Not behind a flag: the defect
    # being fixed IS the invisibility, and an opt-in means whoever needed the traceback did
    # not have it on the run that mattered.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    # INFO is where this codebase reports policy outcomes (a golden reference established, a
    # content completed) — worth seeing. httpx reports every single request at INFO too, and
    # profiling fetches one file per lesson: on a batch that is hundreds of lines of transport
    # noise burying exactly the errors this configuration exists to surface.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # The CLI is its own process and wires the SAME policies as the API: one list, so the
    # two cannot drift again (ADR-0029 §1).
    register_all_policies(dispatcher)
    # And the same schema check, for the same reason: this is the door `evaluate-study` comes
    # through, and a database behind the code turns a paid batch into a traceback halfway.
    schema_version.verify(refuse=get_settings().is_local_auth)

    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed", help="seed rubric v1 + reference data")
    seed_parser.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE)

    role_parser = subparsers.add_parser("set-role", help="assign a role to an assessor")
    role_parser.add_argument("--email", required=True)
    role_parser.add_argument("--role", required=True, choices=[r.value for r in Role])

    import_parser = subparsers.add_parser(
        "import-learnpack", help="bulk register courses from a canonical JSON list"
    )
    import_parser.add_argument("--file", type=Path, required=True)
    import_parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="resolve artifact locators on the filesystem (local packages) instead of HTTP",
    )

    register_parser = subparsers.add_parser(
        "register-package",
        help="register a content version by mechanically discovering a package source (ADR-0027)",
    )
    register_parser.add_argument(
        "--source",
        help="package base URL, or a course directory — absolute, or relative to --root",
    )
    register_parser.add_argument(
        "--generator",
        type=_generator_declaration,
        default=None,
        help="the generator version id for this course, or the literal 'unknown' (ADR-0024)",
    )
    register_parser.add_argument(
        "--format",
        dest="package_format",
        default=LEARNPACK_FORMAT,
        help=f"the source's PackageFormat (default: {LEARNPACK_FORMAT})",
    )
    register_parser.add_argument(
        "--edit-provenance",
        dest="edit_provenance",
        choices=list(EDIT_PROVENANCES),
        default="unknown",
    )
    register_parser.add_argument("--version", default=DEFAULT_VERSION)
    register_parser.add_argument(
        "--consumable-url",
        dest="consumable_url",
        default=None,
        help="declare the http(s) URL of a deployed, human-consumable instance of this "
        "course; a local course usually has none (ADR-0028)",
    )
    register_parser.add_argument(
        "--all",
        action="store_true",
        help="register every course under --root; each course's generator comes from its "
        "parent folder (<name>@<version> | <name>-<version> | unknown)",
    )
    register_parser.add_argument(
        "--root",
        dest="root_key",
        default=BUILTIN_SOURCE_ROOT,
        help="which declared source root to read (LOCAL_SOURCE_ROOTS; default: the repo's "
        f"own {BUILTIN_SOURCE_ROOT}/ tree)",
    )

    workbench_parser = subparsers.add_parser(
        "seed-workbench",
        help="local-only: publish the instruments, accept the extractions, ratify the "
        "assessors and register the generator lineages a manifest declares (ADR-0045)",
    )
    workbench_parser.add_argument("--file", type=Path, default=WORKBENCH_MANIFEST)

    demo_parser = subparsers.add_parser(
        "seed-demo", help="local-only: demo users, courses, campaign and assignments"
    )
    demo_parser.add_argument(
        "--reset",
        action="store_true",
        help="wipe the local dataset first (courses, campaigns, evaluations, local users)",
    )

    import_instrument_parser = subparsers.add_parser(
        "import-instrument", help="create or replace an instrument DRAFT from a YAML spec"
    )
    import_instrument_parser.add_argument("--file", type=Path, required=True)
    import_instrument_parser.add_argument(
        "--revise-definitions",
        action="store_true",
        dest="revise_definitions",
        help="allow changing an existing data requirement's declaration — definition or "
        "value_domain (deliberate act; without it the ADR-0014/0020 lint blocks the import)",
    )

    publish_instrument_parser = subparsers.add_parser(
        "publish-instrument", help="publish a draft instrument (the human act)"
    )
    publish_instrument_parser.add_argument("--id", required=True, dest="instrument_version_id")
    publish_instrument_parser.add_argument(
        "--email", required=True, help="the admin performing the act (published_by)"
    )

    bump_instrument_parser = subparsers.add_parser(
        "bump-instrument",
        help="clone an instrument YAML into the next draft version "
        "(textual: comments and style survive)",
    )
    bump_instrument_parser.add_argument("--file", type=Path, required=True)
    bump_instrument_parser.add_argument(
        "--to", dest="to_version", help="target version (default: v<n> -> v<n+1>)"
    )
    bump_instrument_parser.add_argument("--reason", help="sets revision_reason in the new file")

    profile_parser = subparsers.add_parser(
        "profile-content", help="extract a cited profile for one content (manual)"
    )
    profile_parser.add_argument("--content-id", required=True)
    profile_parser.add_argument(
        "--base-dir", type=Path, help="resolve artifact locators as paths under this dir"
    )

    accept_parser = subparsers.add_parser(
        "accept-extraction", help="accept the current adapter version for a package format"
    )
    accept_parser.add_argument("--package-format", required=True)
    accept_parser.add_argument(
        "--email", required=True, help="the admin performing the act (accepted_by)"
    )

    reprofile_parser = subparsers.add_parser(
        "reprofile", help="explicit batch re-profiling for a package format"
    )
    reprofile_parser.add_argument("--package-format", required=True)
    reprofile_parser.add_argument(
        "--content-id", action="append", dest="content_ids", help="repeatable; default: all"
    )
    reprofile_parser.add_argument("--base-dir", type=Path)

    ratify_parser = subparsers.add_parser(
        "ratify-assessor",
        help="make an instrument version evaluable by an automated assessor (ADR-0019)",
    )
    ratify_parser.add_argument("--name", required=True)
    ratify_parser.add_argument("--version", required=True)
    ratify_parser.add_argument("--instrument-version-id", required=True)
    ratify_parser.add_argument(
        "--email", required=True, help="the admin performing the act (ratified_by)"
    )
    ratify_parser.add_argument(
        "--confirm",
        action="append",
        dest="confirmed",
        default=[],
        metavar="CRITERION_ID",
        help="repeatable: confirm the existing executor realizes a changed/new criterion",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="evaluate a content's profile with an automated assessor"
    )
    evaluate_parser.add_argument("--content-id", required=True)
    evaluate_parser.add_argument("--instrument-version-id", required=True)
    evaluate_parser.add_argument(
        "--assessor",
        required=True,
        help="name:version - always explicit: the registry holds one package per lineage",
    )
    evaluate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="calibration mode: accepts drafts, needs no ratification, persists nothing",
    )

    evaluate_study_parser = subparsers.add_parser(
        "evaluate-study",
        help="evaluate every course of an open study in one bounded, cancellable run",
    )
    evaluate_study_parser.add_argument("--study-id", required=True)
    evaluate_study_parser.add_argument(
        "--assessor",
        default=None,
        help="name:version — optional since the study pins its assessor; if given it must "
        "match the pin, and a disagreement is refused rather than resolved",
    )
    evaluate_study_parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="how many courses to evaluate at a time (default: LLM_MAX_CONCURRENCY). How "
        "many REQUESTS may be in flight is the transport's ceiling either way",
    )
    evaluate_study_parser.add_argument(
        "--re-evaluate",
        action="store_true",
        dest="re_evaluate",
        help="evaluate courses this assessor already evaluated too (default: skip them, so "
        "re-running resumes an interrupted batch)",
    )

    declare_study_parser = subparsers.add_parser(
        "declare-study", help="declare an evaluation study (one named round)"
    )
    declare_study_parser.add_argument("--name", required=True)
    declare_study_parser.add_argument(
        "--description", default=None, help="optional: what this round is for"
    )
    declare_study_parser.add_argument(
        "--instrument-version-id", default=None, help="optional: choose it now or later"
    )
    declare_study_parser.add_argument("--assessor", default=None, help="optional: name:version")
    declare_study_parser.add_argument(
        "--brief-id", action="append", dest="brief_ids", default=None, help="repeatable"
    )
    declare_study_parser.add_argument(
        "--generator-version-id",
        action="append",
        dest="generator_version_ids",
        default=None,
        help="repeatable; which generator versions this round measures. One is a "
        "measurement of that version, several are a comparison between them",
    )
    declare_study_parser.add_argument(
        "--all-generator-versions",
        action="store_true",
        dest="all_generators",
        help="measure every version the briefs bring — said, not left unsaid. Required "
        "before open-study if no --generator-version-id is given",
    )

    update_study_parser = subparsers.add_parser(
        "update-study",
        help="change a draft study: its instrument, its judge, its briefs, "
        "the generator versions it measures (any combination)",
    )
    update_study_parser.add_argument("--study-id", required=True)
    update_study_parser.add_argument(
        "--instrument-version-id", default=None, help="a PUBLISHED version"
    )
    update_study_parser.add_argument(
        "--assessor",
        default=None,
        help=f"name:version — must have ratified the chosen version; {CLEAR_ASSESSOR!r} drops it",
    )
    update_study_parser.add_argument(
        "--brief-id",
        action="append",
        dest="brief_ids",
        default=None,
        help="repeatable; replaces the whole recipe",
    )
    update_study_parser.add_argument(
        "--generator-version-id",
        action="append",
        dest="generator_version_ids",
        default=None,
        help="repeatable; replaces the whole scope",
    )
    update_study_parser.add_argument(
        "--all-generator-versions",
        action="store_true",
        dest="all_generators",
        help="replace the scope with every version the briefs bring",
    )

    open_study_parser = subparsers.add_parser(
        "open-study",
        help="open the study — this is what pins the instrument, the judge and the dataset",
    )
    open_study_parser.add_argument("--study-id", required=True)

    sign_off_study_parser = subparsers.add_parser(
        "sign-off-study",
        help="sign off the study: compose, freeze and sign the report (human act)",
    )
    sign_off_study_parser.add_argument("--study-id", required=True)
    sign_off_study_parser.add_argument(
        "--email", required=True, help="the admin performing the act (signed_off_by)"
    )

    show_report_parser = subparsers.add_parser(
        "show-report", help="print a signed-off study report as JSON"
    )
    show_report_parser.add_argument("--study-id", required=True)

    show_preview_parser = subparsers.add_parser(
        "show-preview",
        help="print the report a study WOULD publish, composed on read — nothing is written",
    )
    show_preview_parser.add_argument("--study-id", required=True)

    show_fitness_parser = subparsers.add_parser(
        "show-fitness",
        help="print the fitness projection of a study (ADR-0023) — optimization, not a judgment",
    )
    show_fitness_parser.add_argument("--study-id", required=True)

    delete_content_parser = subparsers.add_parser(
        "delete-content",
        help="remove a content version nothing has used — local development only (ADR-0033)",
    )
    delete_content_parser.add_argument("--content-id", required=True)

    attribute_parser = subparsers.add_parser(
        "attribute-generator",
        help="record a generator learnt after registration (once, one way — ADR-0024)",
    )
    attribute_parser.add_argument("--content-id", required=True)
    attribute_parser.add_argument("--generator-version-id", required=True)
    attribute_parser.add_argument(
        "--email", required=True, help="the admin performing the act (attributed_by)"
    )

    generator_parser = subparsers.add_parser(
        "register-generator",
        help="mint a generator lineage — the name is typed here and nowhere else (ADR-0031)",
    )
    generator_parser.add_argument("--name", required=True)
    generator_parser.add_argument(
        "--distinct-from",
        default=None,
        metavar="NAME",
        help="the registered name a refusal named, echoed back to declare this is another "
        "generator",
    )

    generator_version_parser = subparsers.add_parser(
        "register-generator-version",
        help="register a version under a registered generator (ADR-0031)",
    )
    # One or the other: a name is the natural handle for a script, an id for anything that
    # just created the lineage. Neither can mint one.
    generator_ref = generator_version_parser.add_mutually_exclusive_group(required=True)
    generator_ref.add_argument("--generator-id", type=UUID)
    generator_ref.add_argument("--generator-name")
    generator_version_parser.add_argument("--version", required=True)
    generator_version_parser.add_argument(
        "--changelog", default=None, help="optional prose for whoever reads a report (ADR-0030)"
    )

    args = parser.parse_args(argv)

    if args.command == "seed":
        if not args.file.exists():
            print(f"seed file not found: {args.file}", file=sys.stderr)
            return 1
        run_seed(args.file)
    elif args.command == "set-role":
        return run_set_role(args.email, args.role)
    elif args.command == "import-learnpack":
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 1
        return run_import_learnpack(args.file, args.base_dir)
    elif args.command == "register-package":
        if args.all:
            if (
                args.source
                or args.generator is not None
                or args.consumable_url
                or args.version != DEFAULT_VERSION
            ):
                print(
                    "--all takes each course's source and generator from the tree; "
                    "--source/--generator/--version/--consumable-url are for single "
                    "registration (one URL cannot declare a deployment for many courses)",
                    file=sys.stderr,
                )
                return 1
            try:
                root = _declared_root(args.root_key)
            except _UndeclaredRoot as exc:
                print(str(exc), file=sys.stderr)
                return 1
            return run_register_package_all(root.path, args.package_format, args.edit_provenance)
        if not args.source or args.generator is None:
            # argparse cannot express "required unless --all"; the generator declaration
            # is never defaulted (ADR-0024).
            print(
                "register-package needs --source and --generator <uuid|unknown>, "
                "or --all for a whole tree",
                file=sys.stderr,
            )
            return 1
        return run_register_package(
            args.source,
            args.generator,
            args.package_format,
            args.edit_provenance,
            args.version,
            args.consumable_url,
            args.root_key,
        )
    elif args.command == "seed-workbench":
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 1
        return run_seed_workbench(args.file)
    elif args.command == "seed-demo":
        return run_seed_demo(args.reset)
    elif args.command == "import-instrument":
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 1
        return run_import_instrument(args.file, args.revise_definitions)
    elif args.command == "publish-instrument":
        return run_publish_instrument(args.instrument_version_id, args.email)
    elif args.command == "bump-instrument":
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 1
        return run_bump_instrument(args.file, args.to_version, args.reason)
    elif args.command == "profile-content":
        return run_profile_content(args.content_id, args.base_dir)
    elif args.command == "accept-extraction":
        return run_accept_extraction(args.package_format, args.email)
    elif args.command == "reprofile":
        return run_reprofile(args.package_format, args.content_ids, args.base_dir)
    elif args.command == "ratify-assessor":
        return run_ratify_assessor(
            args.name, args.version, args.instrument_version_id, args.email, args.confirmed
        )
    elif args.command == "evaluate":
        return run_evaluate(
            args.content_id, args.instrument_version_id, args.assessor, args.dry_run
        )
    elif args.command == "evaluate-study":
        return run_evaluate_study(
            UUID(args.study_id), args.assessor, args.concurrency, args.re_evaluate
        )
    elif args.command == "declare-study":
        return run_declare_study(
            args.name,
            args.description,
            args.instrument_version_id,
            args.assessor,
            [UUID(b) for b in args.brief_ids] if args.brief_ids is not None else None,
            (
                [UUID(g) for g in args.generator_version_ids]
                if args.generator_version_ids is not None
                else None
            ),
            args.all_generators,
        )
    elif args.command == "update-study":
        return run_update_study(
            UUID(args.study_id),
            args.instrument_version_id,
            args.assessor,
            [UUID(b) for b in args.brief_ids] if args.brief_ids is not None else None,
            (
                [UUID(g) for g in args.generator_version_ids]
                if args.generator_version_ids is not None
                else None
            ),
            args.all_generators,
        )
    elif args.command == "open-study":
        return run_open_study(UUID(args.study_id))
    elif args.command == "sign-off-study":
        return run_sign_off_study(UUID(args.study_id), args.email)
    elif args.command == "show-report":
        return run_show_report(UUID(args.study_id))
    elif args.command == "show-preview":
        return run_show_preview(UUID(args.study_id))
    elif args.command == "show-fitness":
        return run_show_fitness(UUID(args.study_id))
    elif args.command == "delete-content":
        return run_delete_content(UUID(args.content_id))
    elif args.command == "attribute-generator":
        return run_attribute_generator(
            UUID(args.content_id), UUID(args.generator_version_id), args.email
        )
    elif args.command == "register-generator":
        return run_register_generator(args.name, args.distinct_from)
    elif args.command == "register-generator-version":
        return run_register_generator_version(
            args.generator_id, args.generator_name, args.version, args.changelog
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
