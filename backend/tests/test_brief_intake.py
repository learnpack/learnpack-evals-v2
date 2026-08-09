"""Mechanical brief intake at registration (ADR-0022).

The ACL derivation is specified pure (bytes → DerivedBrief); the use-case wiring is
specified against the DB: hash dedup pairs registrations, misses register absent, and the
intake never blocks a registration.
"""

import json
from uuid import UUID

import pytest
from sqlalchemy import text

from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.acl_learnpack import derive_brief
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher

SYLLABUS = {
    "courseInfo": {
        "description": "Create an intermediate course on Python object representation.",
        "contentIndex": ["Why repr matters", "repr vs str", "Debugging with repr"],
    }
}
SYLLABUS_BYTES = json.dumps(SYLLABUS).encode("utf-8")


# ------------------------------------------------------------------ pure ACL derivation


def test_derive_brief_extracts_the_operative_instruction():
    derived = derive_brief(SYLLABUS_BYTES)

    assert derived is not None
    assert derived.brief == SYLLABUS["courseInfo"]["description"]
    assert derived.fields["origin"] == "ai_derived_syllabus"
    assert derived.fields["promptRecorded"] is False
    assert derived.fields["materialsHash"]
    assert len(derived.brief_hash) == 64  # sha256 hex


def test_derive_brief_hash_survives_key_reordering():
    reordered = json.dumps(
        {
            "courseInfo": {
                "contentIndex": SYLLABUS["courseInfo"]["contentIndex"],
                "description": SYLLABUS["courseInfo"]["description"],
            }
        }
    ).encode("utf-8")

    assert derive_brief(SYLLABUS_BYTES).brief_hash == derive_brief(reordered).brief_hash


def test_derive_brief_hash_changes_with_the_materials():
    other = json.dumps(
        {
            "courseInfo": {
                "description": SYLLABUS["courseInfo"]["description"],
                "contentIndex": ["A different attachment"],
            }
        }
    ).encode("utf-8")

    assert derive_brief(SYLLABUS_BYTES).brief_hash != derive_brief(other).brief_hash


def test_derive_brief_without_description_returns_none():
    assert derive_brief(b'{"courseInfo": {"contentIndex": []}}') is None
    assert derive_brief(b'{"courseInfo": {"description": "   "}}') is None
    assert derive_brief(b"{}") is None


def test_derive_brief_records_the_declared_materials_source():
    with_source = json.dumps(
        {
            "courseInfo": {
                "description": "A course.",
                "contentIndex": [],
                "materialsSource": "uploaded-pdf",
            }
        }
    ).encode("utf-8")

    assert derive_brief(with_source).fields["materialsSource"] == "uploaded-pdf"
    assert "materialsSource" not in derive_brief(SYLLABUS_BYTES).fields


# ------------------------------------------------------------------ intake adapter


class StubFetcher:
    def __init__(self, payload: bytes | None = None, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error
        self.fetched: list[str] = []

    def fetch(self, locator: str) -> bytes:
        self.fetched.append(locator)
        if self._error is not None:
            raise self._error
        assert self._payload is not None
        return self._payload


SYLLABUS_ARTIFACT = {"kind": "syllabus", "locator": "course/.learn/initialSyllabus.json"}


def test_intake_ignores_other_package_formats():
    intake = PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))

    assert intake.derive("SomethingElseV1", [SYLLABUS_ARTIFACT]) is None


def test_intake_finds_the_syllabus_by_locator_suffix():
    fetcher = StubFetcher(SYLLABUS_BYTES)
    intake = PackageBriefIntake(fetcher)

    derived = intake.derive(
        "LearnpackV1",
        [
            {"kind": "manifest", "locator": "course/learn.json"},
            {"kind": "package_file", "locator": "course/.learn/initialSyllabus.json"},
        ],
    )

    assert derived is not None
    assert fetcher.fetched == ["course/.learn/initialSyllabus.json"]


def test_intake_is_soft_on_fetch_failure():
    intake = PackageBriefIntake(StubFetcher(error=FetchError("boom")))

    assert intake.derive("LearnpackV1", [SYLLABUS_ARTIFACT]) is None


def test_intake_is_soft_on_corrupt_syllabus():
    intake = PackageBriefIntake(StubFetcher(b"not json at all"))

    assert intake.derive("LearnpackV1", [SYLLABUS_ARTIFACT]) is None


class FakeV2Intake:
    """What a future format contributes: locate + derive. One dict entry, nothing else."""

    package_format = "LearnpackV2"

    def locate(self, artifacts):
        return next((a["locator"] for a in artifacts if a.get("kind") == "native-brief"), None)

    def derive(self, payload: bytes):
        from app.modules.evaluand_registry.application.ports import DerivedBrief

        data = json.loads(payload.decode("utf-8"))
        return DerivedBrief(
            brief=data["brief"],
            fields={"origin": "native", "promptRecorded": True},
            brief_hash=data["hash"],
        )


def test_a_new_format_is_one_registry_entry():
    from app.modules.evaluand_registry.infrastructure.brief_intake import (
        BRIEF_INTAKES_BY_FORMAT,
    )

    payload = json.dumps({"brief": "Native commission.", "hash": "a" * 64}).encode("utf-8")
    intake = PackageBriefIntake(
        StubFetcher(payload),
        intakes={**BRIEF_INTAKES_BY_FORMAT, "LearnpackV2": FakeV2Intake()},
    )

    derived = intake.derive(
        "LearnpackV2", [{"kind": "native-brief", "locator": "course/.learn/brief.json"}]
    )
    assert derived is not None
    assert derived.fields["promptRecorded"] is True  # V2's better completeness

    # The V1 entry is untouched by the new one, and unknown formats still miss softly.
    assert "LearnpackV1" in BRIEF_INTAKES_BY_FORMAT
    assert intake.derive("SomethingElseV1", [SYLLABUS_ARTIFACT]) is None


def test_registration_dispatches_by_format_end_to_end(cleanup, unique):
    from app.modules.evaluand_registry.infrastructure.brief_intake import (
        BRIEF_INTAKES_BY_FORMAT,
    )

    payload = json.dumps({"brief": "Native commission.", "hash": f"v2-{unique}"}).encode("utf-8")
    intake = PackageBriefIntake(
        StubFetcher(payload),
        intakes={**BRIEF_INTAKES_BY_FORMAT, "LearnpackV2": FakeV2Intake()},
    )

    content = _register(
        cleanup,
        unique,
        "v2",
        intake=intake,
        package_format="LearnpackV2",
        artifacts=[{"kind": "native-brief", "locator": "course/.learn/brief.json"}],
    )

    assert content.brief_id is not None
    with SessionLocal() as session:
        brief = SqlAlchemyBriefRepository(session).get_by_id(content.brief_id)
        assert brief.fields == {"origin": "native", "promptRecorded": True}


def test_fixture_syllabus_derives_through_the_filesystem_fetcher():
    from app.cli import DEMO_PACKAGES_DIR

    intake = PackageBriefIntake(FilesystemFetcher(DEMO_PACKAGES_DIR))
    derived = intake.derive(
        "LearnpackV1",
        [
            {
                "kind": "syllabus",
                "locator": "introduction-to-generative-ai/.learn/initialSyllabus.json",
            }
        ],
    )

    assert derived is not None
    assert derived.fields["promptRecorded"] is False


# ------------------------------------------------------------------ registration wiring


def _register(
    cleanup,
    unique,
    suffix,
    *,
    intake=None,
    artifacts=None,
    brief_id=None,
    generator_version_id=None,
    package_format="LearnpackV1",
):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        content = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
            brief_intake=intake,
        )(
            RegisterContentVersionCommand(
                package_format=package_format,
                external_id=f"intake-{suffix}-{unique}",
                consumable_url=f"https://intake-{suffix}-{unique}.learn-pack.com/",
                artifacts=artifacts if artifacts is not None else [SYLLABUS_ARTIFACT],
                brief_id=brief_id,
                generator_version_id=generator_version_id,
            )
        )
    cleanup["contents"].append(content.id)
    if content.brief_id and content.brief_id not in cleanup["briefs"]:
        cleanup["briefs"].append(content.brief_id)
    return content


def _brief_events(session, brief_id: UUID) -> int:
    return session.execute(
        text(
            "SELECT count(*) FROM events "
            "WHERE event_type = 'BriefRegistered' AND aggregate_id = :id"
        ),
        {"id": str(brief_id)},
    ).scalar_one()


def test_registration_with_syllabus_creates_the_brief(cleanup, unique):
    content = _register(
        cleanup, unique, "a", intake=PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))
    )

    assert content.brief_id is not None
    with SessionLocal() as session:
        brief = SqlAlchemyBriefRepository(session).get_by_id(content.brief_id)
        assert brief is not None
        assert brief.brief == SYLLABUS["courseInfo"]["description"]
        assert brief.fields["promptRecorded"] is False
        assert brief.brief_hash is not None
        assert _brief_events(session, brief.id) == 1


def test_registrations_with_the_same_syllabus_share_the_brief(cleanup, unique):
    intake = PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))

    first = _register(cleanup, unique, "b1", intake=intake)
    second = _register(cleanup, unique, "b2", intake=intake)

    assert first.brief_id == second.brief_id  # same effective instruction → paired
    with SessionLocal() as session:
        assert _brief_events(session, first.brief_id) == 1  # minted once


def test_registration_without_syllabus_registers_absent(cleanup, unique):
    content = _register(
        cleanup,
        unique,
        "c",
        intake=PackageBriefIntake(StubFetcher(SYLLABUS_BYTES)),
        artifacts=[{"kind": "manifest", "locator": "course/learn.json"}],
    )

    assert content.brief_id is None


def test_registration_survives_a_failing_intake(cleanup, unique):
    content = _register(
        cleanup,
        unique,
        "d",
        intake=PackageBriefIntake(StubFetcher(error=FetchError("network down"))),
    )

    assert content.brief_id is None  # soft failure: registered absent, never blocked


def test_an_explicit_brief_wins_over_intake(cleanup, unique):
    seeded = _register(
        cleanup, unique, "e1", intake=PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))
    )
    other_syllabus = json.dumps(
        {"courseInfo": {"description": "A different commission.", "contentIndex": []}}
    ).encode("utf-8")

    content = _register(
        cleanup,
        unique,
        "e2",
        intake=PackageBriefIntake(StubFetcher(other_syllabus)),
        brief_id=seeded.brief_id,
    )

    assert content.brief_id == seeded.brief_id


def test_registration_without_intake_keeps_the_old_contract(cleanup, unique):
    content = _register(cleanup, unique, "f", intake=None)

    assert content.brief_id is None


@pytest.mark.parametrize("payload", [b"[]", b'"just a string"', b"3"])
def test_derive_brief_returns_none_for_non_course_payloads(payload):
    assert derive_brief(payload) is None


# ------------------------------------------- public read surface for dataset composition


def _register_generator(cleanup, unique):
    from app.modules.evaluand_registry.application.register_generator_version import (
        RegisterGeneratorVersion,
        RegisterGeneratorVersionCommand,
    )

    with SessionLocal() as session:
        uow = UnitOfWork(session)
        generator = RegisterGeneratorVersion(
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(RegisterGeneratorVersionCommand(name=f"intake-gen-{unique}", version="1.0.0"))
    cleanup["generators"].append(generator.id)
    return generator.id


def test_get_available_contents_filters_for_dataset_composition(cleanup, unique):
    from app.modules.evaluand_registry.public import EvaluandRegistryQueries

    intake = PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))
    generator_id = _register_generator(cleanup, unique)
    with_brief = _register(cleanup, unique, "g1", intake=intake)
    linked = _register(cleanup, unique, "g2", intake=intake, generator_version_id=generator_id)
    plain = _register(cleanup, unique, "g3", intake=None, artifacts=[])

    with SessionLocal() as session:
        registry = EvaluandRegistryQueries(session)

        by_brief = registry.get_available_contents(brief_ids=[with_brief.brief_id])
        assert {c.content_id for c in by_brief} == {with_brief.id, linked.id}

        known = registry.get_available_contents(generator_known=True)
        known_ids = {c.content_id for c in known}
        assert linked.id in known_ids
        assert with_brief.id not in known_ids  # unknown generator excluded
        assert plain.id not in known_ids

        by_format = registry.get_available_contents(package_format="LearnpackV1")
        assert {with_brief.id, linked.id, plain.id} <= {c.content_id for c in by_format}

        assert registry.get_available_contents(brief_ids=[]) == []


def test_list_briefs_is_on_the_public_surface(cleanup, unique):
    from app.modules.evaluand_registry.public import EvaluandRegistryQueries

    content = _register(
        cleanup, unique, "h", intake=PackageBriefIntake(StubFetcher(SYLLABUS_BYTES))
    )

    with SessionLocal() as session:
        briefs = EvaluandRegistryQueries(session).list_briefs()
    assert content.brief_id in {b.brief_id for b in briefs}


def test_derive_brief_raises_on_unparseable_bytes():
    # The intake adapter catches this and registers absent (soft failure).
    with pytest.raises(json.JSONDecodeError):
        derive_brief(b"")
