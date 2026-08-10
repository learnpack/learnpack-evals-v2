"""LearnpackV2's own convention, beyond what the format contract kit asserts for every
format: how a generator run's output tree is enumerated, where its identity is composed
from, what it deliberately leaves outside the declared surface, and how a free-text
commission is read. Against the frozen real package. No DB, no network."""

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


# ------------------------------------------------------------------ the commission


def seed_bytes() -> bytes:
    return (FIXTURE / "files/course_brief.md").read_bytes()


def test_the_seed_is_the_commission_verbatim():
    """The seed has no declared shape — whatever the creator wrote is the instruction — so
    nothing is parsed out of it and nothing is normalized into it."""
    derived = LearnpackV2BriefIntake().derive(seed_bytes())

    assert derived is not None
    assert derived.brief == seed_bytes().decode("utf-8")


def test_the_commission_records_that_the_prompt_was_kept():
    """The distinction the study report's caveats are built on: V2 carries the original
    instruction, V1 only a syllabus derived from one."""
    derived = LearnpackV2BriefIntake().derive(seed_bytes())

    assert derived is not None
    assert derived.fields == {"origin": "generation_seed", "promptRecorded": True}


def test_the_same_seed_derives_the_same_identity():
    first = LearnpackV2BriefIntake().derive(seed_bytes())
    second = LearnpackV2BriefIntake().derive(seed_bytes())
    other = LearnpackV2BriefIntake().derive(b"# A different course entirely")

    assert first is not None and second is not None and other is not None
    assert first.brief_hash == second.brief_hash
    assert first.brief_hash != other.brief_hash


def test_the_intake_locates_the_seed_among_the_discovered_artifacts():
    rows = [{"kind": a.kind, "locator": a.locator} for a in discover().artifacts]
    assert LearnpackV2BriefIntake().locate(rows) == "files/course_brief.md"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"   \n\t  ", id="blank"),
        pytest.param(b"\x00 not parseable by any format", id="control bytes"),
        pytest.param(b"\xff\xfe not utf-8", id="undecodable"),
    ],
)
def test_a_payload_that_is_not_a_text_document_registers_the_brief_absent(payload):
    """ADR-0022: a miss is soft. Free text has no parse step to fail, so the check that a
    structured commission gets from its parser has to be stated here."""
    assert LearnpackV2BriefIntake().derive(payload) is None


def test_a_seed_keeps_its_ordinary_whitespace():
    """The rejection above is about control bytes, not about formatting: tabs, newlines and
    trailing spaces are how people write markdown."""
    derived = LearnpackV2BriefIntake().derive(b"# Title\r\n\n\tindented line  \n")

    assert derived is not None
    assert derived.brief == "# Title\r\n\n\tindented line  \n"
