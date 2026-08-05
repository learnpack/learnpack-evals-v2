"""Admin CLI: `python -m app.cli seed | set-role | import-learnpack | seed-demo |
import-instrument | publish-instrument | profile-content | accept-extraction | reprofile`.

The MVP has no rubric authoring UI: `LearnPack Pedagogical Rubric v1` is seeded straight
into a `published`, locked version (07-define.md, "Realización MVP"; 08-code.md §9).

`docs/seed/rubric-v1.json` stays the single source of truth — it is not duplicated inside
/backend. The seed therefore runs locally against Neon, never from the Render container.
"""

import argparse
import json
import sys
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
from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnknownPackageFormat,
)
from app.modules.evaluand_registry.domain.content import InvalidContent
from app.modules.evaluand_registry.domain.metadata import InvalidMetadata
from app.modules.evaluand_registry.infrastructure.acl_learnpack import to_register_command
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
    SqlAlchemyMetadataSchemaRepository,
)
from app.modules.evaluand_registry.public import EvaluandRegistryQueries
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
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_FILE = REPO_ROOT / "docs" / "seed" / "rubric-v1.json"
DEFAULT_REFERENCE_FILE = REPO_ROOT / "docs" / "seed" / "pedagogical-reference.yaml"

# Content metadata is an open collection validated against this schema (ADR-0001).
# The domain never references these keys; only the schema and the UI know them.
LEARNPACK_METADATA_SCHEMA = {
    "packageFormat": "LearnpackV1",
    "keys": {
        "learningObjectives": {"valueType": "string_list", "required": True},
        "targetAudience": {"valueType": "string", "required": True},
        "prerequisites": {"valueType": "string_list", "required": False},
    },
}


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


def seed_metadata_schema(session: Session) -> None:
    session.execute(
        text(
            """
            INSERT INTO metadata_schemas (package_format, spec)
            VALUES (:package_format, :spec)
            ON CONFLICT (package_format) DO UPDATE SET spec = excluded.spec
            """
        ),
        {
            "package_format": LEARNPACK_METADATA_SCHEMA["packageFormat"],
            "spec": json.dumps(LEARNPACK_METADATA_SCHEMA["keys"]),
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
        seed_metadata_schema(session)
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
        f"{criteria_count} criteria, {frameworks_count} frameworks, 1 metadata schema, "
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


def run_import_instrument(spec_file: Path) -> int:
    """Create or replace an instrument DRAFT from an authored YAML (13-code-qa §3.3).

    Publishing stays a separate, human act (`publish-instrument` or the admin endpoint):
    nothing produced by assistance reaches Published without one (design 12, inv. 5).
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
            result = use_case(ImportInstrumentDraftCommand(spec=spec))
        except InstrumentImportError as exc:
            for problem in exc.problems:
                print(f"  LINT  {problem}", file=sys.stderr)
            return 1
        except (InvalidInstrument, InstrumentImmutable) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    instrument = result.instrument
    minted = (
        f", minted data requirements: {', '.join(result.minted_data_requirements)}"
        if result.minted_data_requirements
        else ""
    )
    print(
        f"draft {instrument.id}: {len(instrument.claims)} claims, "
        f"{len(instrument.criteria)} criteria, {len(instrument.bindings)} binding(s){minted}"
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


def run_import_learnpack(seed_file: Path, use_acl: bool) -> int:
    """Bulk-register courses, reusing the `RegisterContentVersion` use case.

    `--acl` routes the payload through `acl_learnpack.to_register_command` (LearnPack's raw
    shape); without it the file is expected in our canonical shape. Which one becomes the
    default depends on the real LearnPack export.
    """
    raw_courses = json.loads(seed_file.read_text(encoding="utf-8"))
    if not isinstance(raw_courses, list):
        print("the file must contain a JSON list of courses", file=sys.stderr)
        return 1

    created = duplicated = failed = 0
    for raw in raw_courses:
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            use_case = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                schemas=SqlAlchemyMetadataSchemaRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
            )
            try:
                command = (
                    to_register_command(raw)
                    if use_acl
                    else RegisterContentVersionCommand(
                        package_format=raw["package_format"],
                        external_id=raw["external_id"],
                        consumable_url=raw["consumable_url"],
                        version=str(raw.get("version", "1")),
                        metadata=raw.get("metadata", {}),
                    )
                )
                content = use_case(command)
                created += 1
                print(f"  created  {content.external_id} v{content.version}")
            except DuplicateContent:
                duplicated += 1
                print(
                    f"  skipped  {raw.get('external_id') or raw.get('slug')} (already registered)"
                )
            except (InvalidContent, InvalidMetadata, UnknownPackageFormat, KeyError) as exc:
                failed += 1
                print(
                    f"  INVALID  {raw.get('external_id') or raw.get('slug')}: {exc}",
                    file=sys.stderr,
                )

    print(f"\n{created} created, {duplicated} already present, {failed} invalid")
    return 1 if failed else 0


# --------------------------------------------------------------------------- seed-demo
# A ready-to-use local dataset (ADR-0008), for contributors who work on rubrics, metrics and
# evaluations and should not need a Clerk account or a Neon database to run the app.
#
# It goes through the real use cases instead of raw INSERTs, so the events are published and
# the policies run exactly as they would in production.

DEMO_INSTRUMENT_VERSION_ID = "learnpack-pedagogical-v1"
DEMO_REQUIRED_EVALUATIONS = 2  # two raters per content: the minimum that yields inter-rater
DEMO_METADATA_VIEW = ["learningObjectives", "targetAudience", "prerequisites"]

# (email, display name, role). `clerk_user_id` mirrors what auth_local builds from the header,
# and the display names are exactly what `display_name_for` derives from these emails — so
# signing in refreshes the profile to the same value instead of silently renaming people.
DEMO_ASSESSORS: list[tuple[str, str, Role]] = [
    ("admin@local.dev", "Admin", Role.ADMIN),
    ("ada.lovelace@local.dev", "Ada Lovelace", Role.EVALUATOR),
    ("grace.hopper@local.dev", "Grace Hopper", Role.EVALUATOR),
]

DEMO_CONTENTS: list[dict[str, Any]] = [
    {
        "package_format": "LearnpackV1",
        "external_id": "introduction-to-generative-ai",
        "version": "1",
        "consumable_url": "https://introduction-to-generative-ai.learn-pack.com/",
        "metadata": {
            "learningObjectives": [
                "Explain how a large language model produces text",
                "Write prompts that constrain a model's output",
                "Recognise when a model is hallucinating",
            ],
            "targetAudience": "Junior developers new to AI",
            "prerequisites": ["Basic Python", "Familiarity with the command line"],
        },
    },
    {
        "package_format": "LearnpackV1",
        "external_id": "object-representation-in-python",
        "version": "1",
        "consumable_url": "https://object-representation-in-python.learn-pack.com/",
        "metadata": {
            "learningObjectives": [
                "Define Python classes with __init__, attributes, and methods that operate "
                "on instance state",
                "Create and use object instances with dot notation",
                "Manipulate collections of objects and objects nested within objects",
            ],
            "targetAudience": (
                "Beginner developers who understand OOP concepts and are ready to write "
                "Python class syntax"
            ),
            "prerequisites": ["Basic Python", "Object-oriented programming concepts"],
        },
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


def _seed_demo_contents() -> dict[str, UUID]:
    """Register the demo courses through `RegisterContentVersion`; reuse them if already there."""
    ids: dict[str, UUID] = {}

    for raw in DEMO_CONTENTS:
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            register = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                schemas=SqlAlchemyMetadataSchemaRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
            )
            try:
                content = register(RegisterContentVersionCommand(**raw))
                ids[raw["external_id"]] = content.id
            except DuplicateContent:
                snapshot = next(
                    s
                    for s in EvaluandRegistryQueries(session).list_content_snapshots()
                    if s.package_format == raw["package_format"]
                    and s.external_id == raw["external_id"]
                    and s.version == raw["version"]
                )
                ids[raw["external_id"]] = snapshot.content_id

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
                metadata_view=DEMO_METADATA_VIEW,
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
        "DELETE FROM criterion_scores",
        "DELETE FROM evaluations",
        "DELETE FROM content_evaluation_completions",
        "DELETE FROM golden_references",
        "DELETE FROM assignments",
        "DELETE FROM campaign_contents",
        "DELETE FROM campaigns",
        "DELETE FROM content_profiles",  # entries/extras cascade; before contents (FK)
        "DELETE FROM extraction_acceptances",
        # App-minted (instrument import), not seeded reference data — wiped so a demo
        # re-import can evolve a draft's definitions without tripping the ADR-0014 lint.
        "DELETE FROM data_requirements",
        "DELETE FROM contents",
        "DELETE FROM events",
        "DELETE FROM assessors WHERE clerk_user_id LIKE 'local|%'",
    ):
        session.execute(text(statement))
    session.commit()


DEMO_INSTRUMENT_SPEC = REPO_ROOT / "docs" / "seed" / "instruments" / "learnpack-course-qa-v1.yaml"


def _seed_demo_acceptance(admin_id: UUID) -> None:
    """Accept the current LearnpackV1 adapter so registration auto-profiles (demo only —
    in the real store this is the team's deliberate act, ADR-0012)."""
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
    """Profile any course the policy did not reach (reused contents emit no event).

    The demo courses carry declared metadata but no package artifacts, so the profiles
    show `lesson_inventory`/`lesson_activities: absent` — the deliberate showcase of
    ADR-0009: absence is a first-class finding, not a gap.
    """
    profiled = 0
    for content_id in content_ids.values():
        with SessionLocal() as session:
            use_case = _build_profile_content(session, base_dir=None)
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

    content_ids = _seed_demo_contents()  # new registrations auto-profile via the policy
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
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed", help="seed rubric v1 + metadata schema")
    seed_parser.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE)

    role_parser = subparsers.add_parser("set-role", help="assign a role to an assessor")
    role_parser.add_argument("--email", required=True)
    role_parser.add_argument("--role", required=True, choices=[r.value for r in Role])

    import_parser = subparsers.add_parser(
        "import-learnpack", help="bulk register courses from a JSON list"
    )
    import_parser.add_argument("--file", type=Path, required=True)
    import_parser.add_argument(
        "--acl",
        action="store_true",
        help="treat the file as LearnPack's raw shape and translate it through the ACL",
    )

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

    publish_instrument_parser = subparsers.add_parser(
        "publish-instrument", help="publish a draft instrument (the human act)"
    )
    publish_instrument_parser.add_argument("--id", required=True, dest="instrument_version_id")
    publish_instrument_parser.add_argument(
        "--email", required=True, help="the admin performing the act (published_by)"
    )

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
        return run_import_learnpack(args.file, args.acl)
    elif args.command == "seed-demo":
        return run_seed_demo(args.reset)
    elif args.command == "import-instrument":
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 1
        return run_import_instrument(args.file)
    elif args.command == "publish-instrument":
        return run_publish_instrument(args.instrument_version_id, args.email)
    elif args.command == "profile-content":
        return run_profile_content(args.content_id, args.base_dir)
    elif args.command == "accept-extraction":
        return run_accept_extraction(args.package_format, args.email)
    elif args.command == "reprofile":
        return run_reprofile(args.package_format, args.content_ids, args.base_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
