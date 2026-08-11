"""Admin CLI: `python -m app.cli seed | set-role | import-learnpack | register-package |
seed-demo | import-instrument | publish-instrument | bump-instrument | profile-content |
accept-extraction | reprofile | ratify-assessor | evaluate | declare-study |
pin-study | compose-dataset | open-study | publish-study | show-report |
attribute-generator | register-generator | register-generator-version`.

The MVP has no rubric authoring UI: `LearnPack Pedagogical Rubric v1` is seeded straight
into a `published`, locked version (07-define.md, "Realización MVP"; 08-code.md §9).

`docs/seed/rubric-v1.json` stays the single source of truth — it is not duplicated inside
/backend. The seed therefore runs locally against Neon, never from the Render container.
"""

import argparse
import json
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
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
from app.modules.evaluand_registry.domain.generator import normalized_name
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
from app.modules.evaluation.domain.model import InvalidAutomatedEvaluation
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, AssessorPackage
from app.modules.evaluation.infrastructure.gateways import (
    DesignInstrumentGateway,
    ProfilingGateway,
)
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
from app.modules.evaluation_studies.application.compose_dataset import (
    ComposeDataset,
    ComposeDatasetCommand,
    UnknownBrief,
)
from app.modules.evaluation_studies.application.declare_study import (
    DeclareStudy,
    DeclareStudyCommand,
)
from app.modules.evaluation_studies.application.fitness import compute_fitness
from app.modules.evaluation_studies.application.open_study import OpenStudy, OpenStudyCommand
from app.modules.evaluation_studies.application.pin_instrument import (
    InstrumentNotPublished,
    PinInstrument,
    PinInstrumentCommand,
    UnknownInstrument,
)
from app.modules.evaluation_studies.application.publish_study import (
    PublishStudy,
    PublishStudyCommand,
)
from app.modules.evaluation_studies.domain.model import (
    DatasetEmpty,
    DatasetLocked,
    InstrumentAlreadyPinned,
    InstrumentNotPinned,
    InvalidStudy,
    StudyAlreadyOpen,
    StudyAlreadyPublished,
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
from app.modules.identity.domain.assessor import Assessor, InvalidAssessor, Kind, Role
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


def run_ratify_assessor(
    name: str, version: str, instrument_version_id: str, email: str, confirmed: list[str]
) -> int:
    """The ADR-0019 act: make one instrument version evaluable by one assessor.

    Initial registration IS the first ratification. Against a later version of the same
    lineage, the diff is computed mechanically (literal pass_condition + required_data):
    unchanged criteria carry their coverage over; changed/new EXECUTED criteria demand an
    explicit `--confirm <criterion_id>`; changed abstained ones are informational (an
    abstention realizes no normative text)."""
    package = _assessor_package(name, version)
    if package is None:
        return 1

    with SessionLocal() as session:
        admin = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if admin is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1

        instruments = SqlAlchemyInstrumentRepository(session)
        target = instruments.get(instrument_version_id)
        if target is None:
            print(f"instrument version {instrument_version_id} not found", file=sys.stderr)
            return 1
        if target.instrument_id != package.instrument_id:
            print(
                f"{name}:{version} owes itself to lineage '{package.instrument_id}', "
                f"not '{target.instrument_id}' (ADR-0019)",
                file=sys.stderr,
            )
            return 1
        if not target.is_published:
            print(
                f"{instrument_version_id} is {target.status}: ratification requires a "
                "published version - calibrate drafts with `evaluate --dry-run`",
                file=sys.stderr,
            )
            return 1

        # Coverage restricted to this version must decide every criterion (ADR-0018).
        version_criteria = {c.criterion_id for c in target.criteria}
        undecided = version_criteria - package.coverage.declared
        if undecided:
            print(
                "coverage does not decide every criterion of the version: "
                f"{', '.join(sorted(undecided))} - executing or abstaining is a change "
                "of the artifact, i.e. a new assessor version (ADR-0016)",
                file=sys.stderr,
            )
            return 1

        assessors = SqlAlchemyAssessorRepository(session)
        row = assessors.get_automated(name, version)
        if row is None:
            row = Assessor(
                id=new_id(),
                clerk_user_id=None,
                display_name=package.display_name,
                kind=Kind.AUTOMATED,
                source_config=package.source_config,
            )
            assessors.add(row)
            print(f"registered automated assessor {package.display_name} ({row.id})")
        elif row.source_config != package.source_config:
            print(
                f"stored source_config of {name}:{version} differs from the code - the "
                "artifact changed without a version bump; bump VERSION (ADR-0016)",
                file=sys.stderr,
            )
            return 1

        ratifications = SqlAlchemyRatificationRepository(session)
        siblings = [
            i.id
            for i in instruments.list_all()
            if i.instrument_id == package.instrument_id and i.id != target.id
        ]
        previous_id = ratifications.latest_ratified(row.id, siblings)
        if previous_id is not None:
            previous = instruments.get(previous_id)
            assert previous is not None  # ratifications FK to instrument_versions
            before = {c.criterion_id: c for c in previous.criteria}
            needs_confirmation: list[str] = []
            for criterion in target.criteria:
                prior = before.get(criterion.criterion_id)
                unchanged = (
                    prior is not None
                    and prior.pass_condition == criterion.pass_condition
                    and prior.required_data == criterion.required_data
                )
                if unchanged:
                    continue
                label = "new" if prior is None else "changed"
                if criterion.criterion_id in package.coverage.abstains:
                    print(f"  {label:8} {criterion.criterion_id}: abstained (no confirm needed)")
                elif criterion.criterion_id in confirmed:
                    print(f"  {label:8} {criterion.criterion_id}: confirmed by {email}")
                else:
                    needs_confirmation.append(criterion.criterion_id)
            if needs_confirmation:
                print(
                    "executed criteria changed since the last ratified version "
                    f"({previous_id}) - confirm the executor still realizes each text "
                    "with: " + " ".join(f"--confirm {c}" for c in needs_confirmation),
                    file=sys.stderr,
                )
                return 1

        newly = ratifications.insert(row.id, target.id, admin.id)
        session.commit()

    if not newly:
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
    if assessor_spec is None or ":" not in assessor_spec:
        # Always explicit since the registry grew past one package: an assessor owes
        # itself to a lineage, and naming which one is doing the judging is part of the act.
        known = ", ".join(f"{n}:{v}" for n, v in sorted(AUTOMATED_ASSESSORS))
        print(f"pass --assessor <name>:<version> (registry has: {known})", file=sys.stderr)
        return 1
    assessor_name, assessor_version = assessor_spec.split(":", 1)
    package = _assessor_package(assessor_name, assessor_version)
    if package is None:
        return 1

    with SessionLocal() as session:
        instruments = DesignInstrumentGateway(session)
        profiles = ProfilingGateway(session)
        if dry_run:
            preview_use_case = PreviewEvaluation(
                instruments=instruments,
                profiles=profiles,
                coverage=package.coverage,
                executors=dict(package.executors),
            )
            try:
                preview = preview_use_case(
                    PreviewEvaluationCommand(
                        content_id=content_id, instrument_version_id=instrument_version_id
                    )
                )
            except (InstrumentNotEvaluable, ProfileNotAvailable) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            _print_outcomes(preview.outcomes, preview.judgment)
            print("dry run: nothing persisted (no evaluation, no events, no judgment)")
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


def _print_outcomes(outcomes, judgment) -> None:  # noqa: ANN001 — CLI presentation only
    width = max(len(o.criterion_id) for o in outcomes)
    for outcome in outcomes:
        origin = "derived " if outcome.derived else "executed"
        detail = ""
        if outcome.failure_mode:
            detail = f"  [{outcome.failure_mode}]"
        elif outcome.quote:
            quote = outcome.quote.replace("\n", " ")
            detail = f'  "{quote[:60]}..."' if len(quote) > 60 else f'  "{quote}"'
        print(f"  {outcome.criterion_id:{width}}  {outcome.outcome:14} {origin}{detail}")
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

COURSES_DIR = REPO_ROOT / "courses"


def _course_root(course_dir: Path) -> FilesystemPackageRoot:
    """A local course's root: locators are minted into the dev mount, so the registered
    package behaves exactly like an http-served one for fetching (brief intake, profiling).
    The course must live under `courses/` — that is the tree the mount serves. It does not
    make the course consumable: a local course registers with no consumable URL (ADR-0028)."""
    try:
        relative = course_dir.resolve().relative_to(COURSES_DIR.resolve())
    except ValueError:
        raise PackageDiscoveryError(
            f"'{course_dir}' is not under {COURSES_DIR.as_posix()}: local sources live in "
            "courses/ (the dev mount serves that tree — see courses/README.md)"
        ) from None
    base = get_settings().local_packages_base_url.rstrip("/")
    return FilesystemPackageRoot(course_dir, locator_base=f"{base}/{relative.as_posix()}")


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
            f"{get_settings().local_packages_base_url}, so without it the brief intake and "
            "profiling would fail silently later.",
            file=sys.stderr,
        )
        return False


def _fixed_root(root: PackageRoot) -> Callable[[str], PackageRoot]:
    def factory(_: str) -> PackageRoot:
        return root

    return factory


def _generator_for_folder(session: Session, folder_name: str) -> UUID | None:
    """Resolve a courses/ generator folder to its declaration. Provisional convention
    (ADR-0027), isolated here so a richer one replaces one function: `<name>@<version>`
    names a **registered** GeneratorVersion, `unknown` declares none (ADR-0024). Anything
    else refuses — mechanical intake never mints generator identities.

    Two steps since ADR-0031, which is also two distinct answers: the lineage may not exist,
    or it may exist without that version. Naming which one is the point."""
    if folder_name == "unknown":
        return None
    name, sep, version = folder_name.rpartition("@")
    if not sep or not name or not version:
        raise UnknownGeneratorVersion(
            f"folder '{folder_name}' is not '<name>@<version>' or 'unknown' (see courses/README.md)"
        )
    generator = SqlAlchemyGeneratorRepository(session).find_by_name_key(normalized_name(name))
    if generator is None:
        raise UnknownGeneratorVersion(
            f"folder '{folder_name}' names no registered generator '{name}' — register it "
            "first (app.cli register-generator)"
        )
    versions = SqlAlchemyGeneratorVersionRepository(session)
    match = next(
        (v for v in versions.list_all() if (v.generator_id, v.version) == (generator.id, version)),
        None,
    )
    if match is None:
        raise UnknownGeneratorVersion(
            f"generator '{generator.name}' has no registered version '{version}' — register it "
            "first (app.cli register-generator-version)"
        )
    return match.id


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
) -> int:
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
    except (PackageDiscoveryError, InvalidContent, UnknownGeneratorVersion) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"{status}  {detail}")
    # Single-source registration is what a human runs while debugging one course — exactly
    # when "did it profile?" is the question.
    _report_profiling([content_id] if status == "created" else [])
    return 0


def run_register_package_all(courses_dir: Path, package_format: str, edit_provenance: str) -> int:
    """Batch local intake: every `courses/<generator-folder>/<course>/` registers through
    the same use case — batch is a loop, not another path (ADR-0027)."""
    if not courses_dir.is_dir():
        print(
            f"'{courses_dir.as_posix()}' does not exist — create "
            "courses/<name>@<version>/<course>/ first (see courses/README.md)",
            file=sys.stderr,
        )
        return 1

    generator_dirs = sorted(d for d in courses_dir.iterdir() if d.is_dir())
    course_dirs = [
        (folder, course)
        for folder in generator_dirs
        for course in sorted(d for d in folder.iterdir() if d.is_dir())
    ]
    if not course_dirs:
        print(f"no courses found under {courses_dir.as_posix()}")
        return 0

    # A tree-wide declaration deserves a tree-wide check (the ADR-0024 pattern): every
    # generator folder resolves before anything registers, so a typo is one clean abort.
    generators_by_folder: dict[str, UUID | None] = {}
    problems: list[str] = []
    with SessionLocal() as session:
        for folder in generator_dirs:
            try:
                generators_by_folder[folder.name] = _generator_for_folder(session, folder.name)
            except UnknownGeneratorVersion as exc:
                problems.append(str(exc))
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("nothing was registered", file=sys.stderr)
        return 1

    if not _mount_preflight(_course_root(course_dirs[0][1]), course_dirs[0][1]):
        return 1

    created_ids: list[UUID] = []
    created = unchanged = conflicts = invalid = 0
    for folder, course_dir in course_dirs:
        label = f"{folder.name}/{course_dir.name}"
        try:
            root = _course_root(course_dir)
            status, detail, content_id = _register_package(
                str(course_dir),
                _fixed_root(root),
                generators_by_folder[folder.name],
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
        if status == "created":
            created_ids.append(content_id)
        print(f"  {status}  {detail}")

    print(f"\n{created} created, {unchanged} unchanged, {conflicts} conflicts, {invalid} invalid")
    _report_profiling(created_ids)
    # A failed profile is not a failed registration: the evaluand is registered either way
    # (the hard/soft split of ADR-0027 §3). The exit code stays about registration.
    return 1 if conflicts or invalid else 0


# --------------------------------------------------------------------------- studies
# The manual loop (13-code §3.6): declare → pin → compose → open → publish → show-report.
# Studies never command Orchestration — the wiring between rounds is this actor's.

_STUDY_ERRORS = (
    StudyNotFound,
    InvalidStudy,
    InstrumentAlreadyPinned,
    InstrumentNotPinned,
    InstrumentNotPublished,
    UnknownInstrument,
    UnknownBrief,
    DatasetLocked,
    DatasetEmpty,
    StudyAlreadyOpen,
    StudyNotOpen,
    StudyAlreadyPublished,
)


def run_declare_study(purpose: str) -> int:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        try:
            study = DeclareStudy(SqlAlchemyStudyRepository(session), uow.events, uow)(
                DeclareStudyCommand(purpose=purpose)
            )
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"declared study {study.id}")
    return 0


def run_pin_study(study_id: UUID, instrument_version_id: str) -> int:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = PinInstrument(
            studies=SqlAlchemyStudyRepository(session),
            instruments=StudiesDesignGateway(session),
            publisher=uow.events,
            uow=uow,
        )
        try:
            study = use_case(
                PinInstrumentCommand(study_id=study_id, instrument_version_id=instrument_version_id)
            )
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"pinned {instrument_version_id} to study {study.id} ({study.status})")
    return 0


def run_compose_dataset(study_id: UUID, brief_ids: list[UUID]) -> int:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = ComposeDataset(
            studies=SqlAlchemyStudyRepository(session),
            registry=StudiesRegistryGateway(session),
            uow=uow,
        )
        try:
            study = use_case(ComposeDatasetCommand(study_id=study_id, brief_ids=brief_ids))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(
        f"composed study {study.id}: {len(study.brief_ids)} briefs -> "
        f"{len(study.content_ids)} contents ({study.status})"
    )
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


def run_publish_study(study_id: UUID, email: str) -> int:
    """The human act: compose the report from the current judgments and freeze it."""
    with SessionLocal() as session:
        assessor = SqlAlchemyAssessorRepository(session).get_by_email(email)
        if assessor is None:
            print(f"no assessor with email {email!r}", file=sys.stderr)
            return 1
        uow = UnitOfWork(session)
        use_case = PublishStudy(
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
            study = use_case(PublishStudyCommand(study_id=study_id, published_by=assessor.id))
        except _STUDY_ERRORS as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"published study {study.id} (by {email}) — the report is now immutable")
    return 0


def run_show_report(study_id: UUID) -> int:
    with SessionLocal() as session:
        dto = SqlAlchemyStudyReportRepository(session).get(study_id)
    if dto is None:
        print(f"study {study_id} has no published report", file=sys.stderr)
        return 1
    print(json.dumps(dto.report, indent=2))
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
            generators=generators,
            judgments=(
                evaluation.get_judgments(content_ids, instrument_version_id)
                if instrument_version_id
                else []
            ),
            outcomes=(
                evaluation.get_criterion_outcomes(content_ids, instrument_version_id)
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


def _demo_local_mode_only() -> bool:
    """The guard that keeps demo data out of the real store.

    `seed-demo` writes wherever DATABASE_URL points, so it refuses to run unless the process
    is configured for local development.
    """
    if get_settings().is_local_auth:
        return True
    print(
        "seed-demo only runs with AUTH_MODE=local: it writes demo users, courses and a "
        "campaign, which must never land in a real database.",
        file=sys.stderr,
    )
    return False


def _seed_demo_assessors(session: Session) -> dict[str, UUID]:
    """Create the demo users, and align the role of any that already exist.

    Aligning matters: signing in as `admin@local.dev` before seeding creates that assessor as
    an `evaluator` (ResolveAssessor's default). Leaving it would make this command print
    "admin" for someone who then gets 403 everywhere. This is a seeder, not a login path — the
    ADR-0007 invariant it must not break is that *logging in* never changes a role.
    """
    repository = SqlAlchemyAssessorRepository(session)
    ids: dict[str, UUID] = {}

    for email, display_name, role in DEMO_ASSESSORS:
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
        ids[email] = assessor.id

    return ids


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
    if not _demo_local_mode_only():
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
        "--source", help="package base URL, or a course directory under courses/"
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
        help="register every course under --courses-dir; each course's generator comes "
        "from its parent folder (<name>@<version> | unknown)",
    )
    register_parser.add_argument("--courses-dir", type=Path, default=COURSES_DIR)

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

    declare_study_parser = subparsers.add_parser(
        "declare-study", help="declare an evaluation study (the round with a purpose)"
    )
    declare_study_parser.add_argument("--purpose", required=True)

    pin_study_parser = subparsers.add_parser(
        "pin-study", help="pin a published instrument version to a study (once, before open)"
    )
    pin_study_parser.add_argument("--study-id", required=True)
    pin_study_parser.add_argument("--instrument-version-id", required=True)

    compose_dataset_parser = subparsers.add_parser(
        "compose-dataset", help="compose the study dataset: briefs -> registered contents"
    )
    compose_dataset_parser.add_argument("--study-id", required=True)
    compose_dataset_parser.add_argument(
        "--brief-id", action="append", dest="brief_ids", default=[], help="repeatable"
    )

    open_study_parser = subparsers.add_parser(
        "open-study", help="open the study — the dataset is fixed from here on"
    )
    open_study_parser.add_argument("--study-id", required=True)

    publish_study_parser = subparsers.add_parser(
        "publish-study", help="publish the study: compose and freeze the report (human act)"
    )
    publish_study_parser.add_argument("--study-id", required=True)
    publish_study_parser.add_argument(
        "--email", required=True, help="the admin performing the act (published_by)"
    )

    show_report_parser = subparsers.add_parser(
        "show-report", help="print a published study report as JSON"
    )
    show_report_parser.add_argument("--study-id", required=True)

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
                    "--all takes each course's source and generator from the courses/ "
                    "tree; --source/--generator/--version/--consumable-url are for single "
                    "registration (one URL cannot declare a deployment for many courses)",
                    file=sys.stderr,
                )
                return 1
            return run_register_package_all(
                args.courses_dir, args.package_format, args.edit_provenance
            )
        if not args.source or args.generator is None:
            # argparse cannot express "required unless --all"; the generator declaration
            # is never defaulted (ADR-0024).
            print(
                "register-package needs --source and --generator <uuid|unknown>, "
                "or --all for the courses/ tree",
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
        )
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
    elif args.command == "declare-study":
        return run_declare_study(args.purpose)
    elif args.command == "pin-study":
        return run_pin_study(UUID(args.study_id), args.instrument_version_id)
    elif args.command == "compose-dataset":
        return run_compose_dataset(UUID(args.study_id), [UUID(b) for b in args.brief_ids])
    elif args.command == "open-study":
        return run_open_study(UUID(args.study_id))
    elif args.command == "publish-study":
        return run_publish_study(UUID(args.study_id), args.email)
    elif args.command == "show-report":
        return run_show_report(UUID(args.study_id))
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
