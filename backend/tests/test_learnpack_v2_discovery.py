"""LearnpackV2's own convention, beyond what the format contract kit asserts for every
format: how a generator run's output tree is enumerated, where its identity is composed
from, what it deliberately leaves outside the declared surface, and how the request it was
started from is read. Against the frozen real package. No DB, no network."""

import json
import shutil
from pathlib import Path

import pytest

from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.infrastructure.brief_intake import LearnpackV2BriefIntake
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    LearnpackV2Discovery,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "learnpack_v2" / "03-html-fundamentals-20260810191731"
)


def discover(package_dir: Path = FIXTURE, locator_base: str | None = None):
    return LearnpackV2Discovery().discover(
        FilesystemPackageRoot(package_dir, locator_base=locator_base)
    )


def edited(tmp_path: Path, relative_path: str, mutate) -> Path:
    """A copy of the fixture with one file rewritten by `mutate`, which receives the parsed
    JSON and returns what to write — how every hard-failure case below drifts the package."""
    copy = tmp_path / FIXTURE.name
    if not copy.exists():
        shutil.copytree(FIXTURE, copy)
    target = copy / relative_path
    target.write_text(json.dumps(mutate(json.loads(target.read_text(encoding="utf-8")))))
    return copy


def locators(discovered, kind: str) -> list[str]:
    return [a.locator for a in discovered.artifacts if a.kind == kind]


# ------------------------------------------------------------------ lesson enumeration


def test_the_plan_ids_resolve_to_bodies_through_the_stats_slug():
    """The chain that makes directory listing unnecessary: `lesson_plan.json` lists ids,
    each id's `processing_stats` file names its body. Neither half alone is enough — the
    plan never states a filename, and the stats are only reachable by id."""
    plan = json.loads((FIXTURE / "files/lesson_plan.json").read_text(encoding="utf-8"))
    ids = [lesson["id"] for lesson in plan["lessons"]]
    expected_bodies = [
        "lessons/{}.md".format(
            json.loads(
                (FIXTURE / f"files/processing_stats/{lesson_id}.json").read_text(encoding="utf-8")
            )["lesson_slug"]
        )
        for lesson_id in ids
    ]

    discovered = discover()

    assert locators(discovered, "lesson_content") == expected_bodies
    assert locators(discovered, "lesson_brief") == [f"files/lesson_briefs/{i}.json" for i in ids]
    assert locators(discovered, "lesson_stats") == [f"files/processing_stats/{i}.json" for i in ids]


def test_every_lesson_the_plan_declares_is_discovered():
    plan = json.loads((FIXTURE / "files/lesson_plan.json").read_text(encoding="utf-8"))
    assert len(locators(discover(), "lesson_content")) == len(plan["lessons"])


def test_the_descriptor_is_the_planned_course_title():
    assert discover().title == "HTML Fundamentals: Building Web Page Structure"


def test_a_lesson_whose_stats_declare_no_slug_refuses_the_package(tmp_path):
    """Hard-failing (ADR-0027): the body cannot be located, so the package is not
    registered — half an enumeration would silently shrink the evaluand."""
    drifted = edited(
        tmp_path, "files/processing_stats/01.0.json", lambda s: {**s, "lesson_slug": ""}
    )
    with pytest.raises(PackageDiscoveryError, match="lesson_slug"):
        discover(drifted)


def test_a_slug_naming_no_body_refuses_the_package(tmp_path):
    drifted = edited(
        tmp_path, "files/processing_stats/01.0.json", lambda s: {**s, "lesson_slug": "not-a-lesson"}
    )
    with pytest.raises(PackageDiscoveryError):
        discover(drifted)


def test_a_plan_without_a_lessons_list_refuses_the_package(tmp_path):
    drifted = edited(tmp_path, "files/lesson_plan.json", lambda p: {**p, "lessons": None})
    with pytest.raises(PackageDiscoveryError, match="no lessons list"):
        discover(drifted)


def test_a_lesson_without_an_id_refuses_the_package(tmp_path):
    drifted = edited(
        tmp_path,
        "files/lesson_plan.json",
        lambda p: {**p, "lessons": [{k: v for k, v in p["lessons"][0].items() if k != "id"}]},
    )
    with pytest.raises(PackageDiscoveryError, match="without an id"):
        discover(drifted)


# ------------------------------------------------------------------ the declared surface


class RecordingRoot:
    """A root that remembers what was asked of it — the way to assert an exclusion, which
    the fixture's contents cannot prove on their own."""

    def __init__(self, package_dir: Path) -> None:
        self._inner = FilesystemPackageRoot(package_dir)
        self.requested: list[str] = []

    def fetch(self, relative_path: str) -> bytes:
        self.requested.append(relative_path)
        return self._inner.fetch(relative_path)

    def locator_for(self, relative_path: str) -> str:
        return self._inner.locator_for(relative_path)

    @property
    def consumable_url(self) -> str | None:
        return self._inner.consumable_url


def test_discovery_never_reads_the_run_log_or_the_generator_config():
    """`logs/` is run telemetry down to absolute paths on the machine that produced it, and
    `config/agents.yml` is the generator describing itself (ADR-0030). Neither is the
    evaluand, so neither is fetched — and so neither can move the content hash."""
    root = RecordingRoot(FIXTURE)
    LearnpackV2Discovery().discover(root)

    assert [p for p in root.requested if p.startswith(("logs/", "config/"))] == []
    assert (FIXTURE / "config" / "agents.yml").exists()  # present, and still ignored


def test_every_fetched_file_is_registered_as_an_artifact():
    """No silent reads: what discovery fetched is exactly what it declared, so the hash
    covers the surface a reader can see."""
    root = RecordingRoot(FIXTURE)
    discovered = LearnpackV2Discovery().discover(root)

    assert sorted(root.requested) == sorted(a.locator for a in discovered.artifacts)


# ------------------------------------------------------------------ composed identity


def test_the_external_id_composes_the_seed_and_the_run_start():
    assert discover().external_id == "03-html-fundamentals-20260810184810"


def test_the_external_id_is_independent_of_where_the_tree_sits(tmp_path):
    """Composed from the run's own declaration, not from the directory name — so moving or
    renaming the tree does not mint a second content."""
    moved = tmp_path / "renamed-by-somebody"
    shutil.copytree(FIXTURE, moved)
    assert discover(moved).external_id == discover().external_id


def test_a_run_start_in_another_offset_reads_the_same_instant(tmp_path):
    """Normalized to UTC: the same instant declared differently is the same run."""
    drifted = edited(
        tmp_path,
        "traces/run_metadata.json",
        lambda m: {**m, "started_at": "2026-08-10T15:48:10-03:00"},
    )
    assert discover(drifted).external_id == discover().external_id


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: {**m, "system_metadata": {}}, "no run seed id"),
        (lambda m: {**m, "system_metadata": {"run_info": {"seed_id": "  "}}}, "no run seed id"),
        (lambda m: {k: v for k, v in m.items() if k != "started_at"}, "no run start"),
        (lambda m: {**m, "started_at": "the tenth of August"}, "unreadable run start"),
    ],
)
def test_an_undeclared_identity_refuses_the_package(tmp_path, mutate, message):
    with pytest.raises(PackageDiscoveryError, match=message):
        discover(edited(tmp_path, "traces/run_metadata.json", mutate))


# ------------------------------------------------------------------ the declared generator


def test_the_declared_generator_is_the_system_name_and_version_verbatim():
    """Evidence to cross-check a registration's declared generator against, taken exactly as
    the run manifest states it — including a dev build's dirty git description, which is
    exactly the kind of value nothing here should normalize or parse as a semver."""
    discovered = discover()
    assert discovered.declared_generator_name == "learnpack-generator"
    assert discovered.declared_generator_version == "59a1591-dirty"


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda m: {k: v for k, v in m.items() if k != "system_name"}, id="no name"),
        pytest.param(lambda m: {**m, "system_name": "   "}, id="blank name"),
        pytest.param(
            lambda m: {k: v for k, v in m.items() if k != "system_version"}, id="no version"
        ),
        pytest.param(lambda m: {**m, "system_version": ""}, id="blank version"),
    ],
)
def test_a_missing_declared_generator_is_absent_not_a_refusal(tmp_path, mutate):
    """Soft, unlike every other read in this class (ADR-0027's "no soft spot" is about the
    course's own commission, not this new, optional cross-check): a package that predates
    this field, or a format that never declares one, still registers — the comparison simply
    has nothing to compare."""
    discovered = discover(edited(tmp_path, "traces/run_metadata.json", mutate))
    assert discovered.declared_generator_name is None
    assert discovered.declared_generator_version is None


# ------------------------------------------------------------------ the commission


def request_bytes() -> bytes:
    return (FIXTURE / "files/course_request.json").read_bytes()


def request_content() -> str:
    return json.loads(request_bytes().decode("utf-8"))["content"]


def test_the_request_is_the_commission_verbatim():
    """The envelope is structure; the commission inside it is not. Whatever the creator
    wrote is the instruction, so nothing is read out of `content` and nothing is
    normalized into it — trailing spaces and line breaks included."""
    derived = LearnpackV2BriefIntake().derive(request_bytes())

    assert derived is not None
    assert derived.brief == request_content()
    assert derived.brief.startswith("Title: ")


def test_the_commission_records_that_the_prompt_was_kept():
    """The distinction the study report's caveats are built on: V2 carries the original
    instruction, V1 only a syllabus derived from one."""
    derived = LearnpackV2BriefIntake().derive(request_bytes())

    assert derived is not None
    assert derived.fields == {"origin": "generation_seed", "promptRecorded": True}


def test_the_identity_is_the_request_not_its_envelope():
    """The commission's identity is the instruction, so the same request re-wrapped — extra
    keys, different formatting — is the same brief and cannot mint a second one."""
    rewrapped = json.dumps(
        {"content": request_content(), "emitted_by": "some later envelope"}, indent=4
    ).encode("utf-8")

    first = LearnpackV2BriefIntake().derive(request_bytes())
    again = LearnpackV2BriefIntake().derive(rewrapped)
    other = LearnpackV2BriefIntake().derive(b'{"content": "A different course entirely"}')

    assert first is not None and again is not None and other is not None
    assert first.brief_hash == again.brief_hash
    assert first.brief_hash != other.brief_hash


def test_the_intake_locates_the_request_among_the_discovered_artifacts():
    rows = [{"kind": a.kind, "locator": a.locator} for a in discover().artifacts]
    assert LearnpackV2BriefIntake().locate(rows) == "files/course_request.json"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b'{"content": ""}', id="empty content"),
        pytest.param(b'{"content": "   \\n\\t  "}', id="blank content"),
        pytest.param(b'{"content": null}', id="null content"),
        pytest.param(b'{"content": {"nested": "object"}}', id="content is not text"),
        pytest.param(b'{"request": "under another key"}', id="no content key"),
        pytest.param(b'["not", "an", "envelope"]', id="not an object"),
    ],
)
def test_an_envelope_with_no_request_registers_the_brief_absent(payload):
    """ADR-0022: a miss is soft — the content registers with its brief absent, which is a
    recorded state. Payloads that are not JSON at all are the port's business, and the
    format contract kit pins that they never escape either."""
    assert LearnpackV2BriefIntake().derive(payload) is None
