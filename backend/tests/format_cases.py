"""One `FormatCase` per registered package format — the data half of the format
contract kit (`test_format_contract.py`), and the executable companion of the
"Adding a package format" runbook in `backend/README.md`.

A case declares WHAT the contract suite should observe over a format's frozen fixture;
the suite supplies the HOW once, for every format. A format registered in any of the
per-format registries without a case here fails the suite — the kit cannot be skipped
by omission.

Expectations are written as literals on purpose: importing them from the adapter under
test would make every assertion tautological.
"""

from dataclasses import dataclass
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class FormatCase:
    package_format: str
    # The frozen real package the contract runs against (runbook step 1). It should
    # exercise the format's full surface: every artifact kind, and the commission if
    # the format carries one.
    fixture_dir: Path
    # The identity the package itself declares — never typed into a form (ADR-0027).
    expected_external_id: str
    # The artifact `kind` vocabulary this format's discovery writes (sole writer).
    expected_artifact_kinds: frozenset[str]
    # Whether registering the fixture derives a `GenerationBrief` (ADR-0022). Named for
    # the domain concept, not the carrier — LearnpackV1's carrier is its syllabus.
    expects_brief: bool
    # The `DataRequirement` ids the extraction adapter declares (ADR-0014/0020).
    # None = no extraction adapter yet (runbook step 3 pending): extraction tests skip,
    # discovery and registration tests still run — the incremental landing is legal.
    expected_capabilities: frozenset[str] | None


FORMAT_CASES: dict[str, FormatCase] = {
    case.package_format: case
    for case in (
        FormatCase(
            package_format="LearnpackV1",
            fixture_dir=FIXTURES / "learnpack_v1" / "introduction-to-generative-ai",
            expected_external_id="introduction-to-generative-ai",
            expected_artifact_kinds=frozenset(
                {"manifest", "package_manifest", "syllabus", "lesson_content", "lesson_file"}
            ),
            expects_brief=True,
            expected_capabilities=frozenset(
                {
                    "course_descriptor",
                    "lesson_inventory",
                    "lesson_bodies",
                    "lesson_activities",
                    "lesson_assessment_items",
                }
            ),
        ),
        FormatCase(
            package_format="LearnpackV2",
            fixture_dir=FIXTURES / "learnpack_v2" / "03-html-fundamentals-20260810191731",
            # Composed from what the run declares about itself — the tree carries no slug.
            # Deliberately not the directory name, which the fixture still spells out.
            expected_external_id="03-html-fundamentals-20260810184810",
            expected_artifact_kinds=frozenset(
                {
                    "run_manifest",
                    "user_intent",
                    "course_value",
                    "concept_graph",
                    "coverage_check",
                    "course_request",
                    "lesson_plan",
                    "lesson_brief",
                    "lesson_stats",
                    "lesson_content",
                }
            ),
            # The seed the run was started from, embedded verbatim.
            expects_brief=True,
            # Neither `lesson_activities` nor `prerequisites`: a run's output carries
            # exercise *proposals* rather than exercises, and its concept prerequisites are
            # between concepts, not entry requirements. Both derive `not_applicable`. The
            # proposals themselves are supplied — under `assessment_offerings`, marked as
            # proposed beside what the package delivers (ADR-0046).
            expected_capabilities=frozenset(
                {
                    "course_descriptor",
                    "lesson_inventory",
                    "lesson_bodies",
                    "lesson_assessment_items",
                    "assessment_offerings",
                    "learning_objectives",
                    "declared_objectives",
                    "lesson_concept_coverage",
                    "target_audience",
                }
            ),
        ),
    )
}
