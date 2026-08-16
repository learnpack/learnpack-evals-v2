"""One generation, folder to score: what `measure` chains, and what it refuses to guess.

The evaluation itself is faked at `batch_runs._run_use_case` — the same seam
`test_batch_runs.py` uses. What is pinned here is the chaining: that a folder becomes a
registered, profiled dataset; that the round's scope is the one version the folder names;
that the norm and the judge are derived only when the derivation has one answer; and that
running it again resumes the round instead of declaring a second one over the same courses.

No server runs, so the mount is served off disk — the locators stay genuine http URLs and
only the transport changes, exactly as in `test_local_courses_dev_api.py`.
"""

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

import app.cli as cli
from app.cli import run_measure
from app.config import get_settings
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.evaluand_registry.infrastructure import local_sources
from app.platform import batch_runs
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher

V2_FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v2"
V2_RUN = "03-html-fundamentals-20260810191731"
INSTRUMENTS = Path(__file__).resolve().parents[2] / "docs" / "seed" / "instruments"
DRAFTS_SPEC = INSTRUMENTS / "course-drafts-qa-v6.yaml"
COURSE_SPEC = INSTRUMENTS / "learnpack-course-qa-v1.yaml"


@pytest.fixture
def runs_root(tmp_path, monkeypatch, requires_db):
    """One declared root holding the generations, and a `courses/` tree that is not the
    repo's — so nothing here can register against the real one."""
    monkeypatch.setattr(local_sources, "COURSES_DIR", tmp_path / "courses")
    (tmp_path / "courses").mkdir()
    tree = tmp_path / "runs"
    tree.mkdir()
    monkeypatch.setenv("LOCAL_SOURCE_ROOTS", f"runs={tree}")
    get_settings.cache_clear()
    yield tree
    get_settings.cache_clear()


@pytest.fixture
def served(monkeypatch):
    """Resolve every declared root's mount URLs off disk, for the brief intake, the mount
    preflight and the profiling policy alike."""

    class MountFetcher:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fetch(self, locator: str) -> bytes:
            for root in local_sources.configured_roots():
                base = f"{root.url_base}/"
                if locator.startswith(base):
                    return FilesystemFetcher(root.path).fetch(locator.removeprefix(base))
            raise FetchError(f"nothing serves '{locator}'")

    from app.modules.content_profiling.infrastructure import policies as profiling_policies

    monkeypatch.setattr(cli, "HttpFetcher", MountFetcher)
    monkeypatch.setattr(profiling_policies, "HttpPackageFetcher", MountFetcher)


@pytest.fixture
def accepted_v2(cleanup):
    """Arm auto-profiling for the current LearnpackV2 adapter. Global, hence tracked."""
    from app.platform.db import SessionLocal

    adapter = ADAPTERS_BY_FORMAT["LearnpackV2"]
    cleanup["acceptances"].append(("LearnpackV2", adapter.adapter_version))
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO extraction_acceptances (package_format, adapter_version, accepted_by)"
                " VALUES ('LearnpackV2', :version, :by) ON CONFLICT DO NOTHING"
            ),
            {"version": adapter.adapter_version, "by": uuid4()},
        )
        session.commit()


@pytest.fixture
def norm(cleanup, session, unique):
    """A published instrument bound to LearnpackV2, and ONE assessor ratified against it.

    The other lineage is imported first because this one declares only the two ids it mints
    and requires seven that lineage minted (ADR-0014) — which is also why the workbench
    manifest lists them in that order. Both are imported from the real files: a placeholder
    namespace would then collide with the definitions these YAMLs carry.

    `drafts-structural` rather than `drafts-hybrid`: it carries no LLM, so even a test that
    let the real evaluation run could not reach the network. One of the two on purpose — the
    ambiguity of several is its own test.
    """
    from app.cli import _instrument_identity, run_publish_instrument
    from app.modules.identity.domain.assessor import Role
    from app.platform.db import SessionLocal

    cleanup["instruments"].append(_instrument_identity(COURSE_SPEC)[1])
    assert cli.run_import_instrument(COURSE_SPEC) == 0

    _, version_id = _instrument_identity(DRAFTS_SPEC)
    cleanup["instruments"].append(version_id)
    assert cli.run_import_instrument(DRAFTS_SPEC) == 0

    email = f"norm-admin-{unique}@example.com"
    with SessionLocal() as s:
        admin_id = cli._ensure_local_assessor(s, email, "Norm Admin", Role.ADMIN)
    cleanup["assessors"].append(admin_id)
    assert run_publish_instrument(version_id, email) == 0
    assert cli.run_ratify_assessor("drafts-structural", "1", version_id, email, []) == 0

    row = session.execute(
        text("SELECT id FROM assessors WHERE source_config->>'name' = 'drafts-structural'")
    ).scalar()
    cleanup["assessors"].append(row)
    return version_id


@pytest.fixture
def generation(runs_root, register_generator_version, unique, cleanup):
    """A folder named the way a generator names its own output, holding one course.

    The version in the folder name is NOT registered here: registering it is what the intake
    does when it reads the folder, and the teardown collects whatever that produced — the
    lineage cannot be deleted while a version still points at it.
    """
    name = f"measure-gen-{unique}"
    register_generator_version(name, "1.0.0")
    folder = f"{name}-9c1f2ab-dirty"
    shutil.copytree(V2_FIXTURES / V2_RUN, runs_root / folder / V2_RUN)
    yield folder

    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        for row in s.execute(
            text(
                "SELECT v.id FROM generator_versions v JOIN generators g ON g.id = v.generator_id"
                " WHERE g.name = :name"
            ),
            {"name": name},
        ):
            if row.id not in cleanup["generators"]:
                cleanup["generators"].append(row.id)


@pytest.fixture
def no_llm(monkeypatch):
    """The batch runs; the evaluation inside it does not. `EvaluateContent` has its own
    tests, and what this file is about is the layer that chains them."""
    judged: list[str] = []

    def fake(run, content):
        judged.append(content.external_id)
        return uuid4()

    monkeypatch.setattr(batch_runs, "_run_use_case", fake)
    return judged


def measured_study(session, name):
    """The round this generation produced, with everything it wrote tracked for cleanup. The
    course's `external_id` is the package's own — the folder name is not it — so the dataset
    is what the contents are found through."""
    return session.execute(
        text("SELECT id, status, instrument_version_id FROM studies WHERE name = :n"), {"n": name}
    ).first()


def track(cleanup, session, study) -> None:
    if study.id not in cleanup["studies"]:
        cleanup["studies"].append(study.id)
    for row in session.execute(
        text("SELECT content_id FROM study_dataset WHERE study_id = :id"), {"id": study.id}
    ):
        if row.content_id not in cleanup["contents"]:
            cleanup["contents"].append(row.content_id)


# ---------------------------------------------------------------------------- the chain


def test_a_folder_becomes_a_round_and_a_score(
    generation, served, accepted_v2, norm, no_llm, cleanup, session, capsys
):
    assert (
        run_measure(
            root_key="runs",
            path=generation,
            package_format="LearnpackV2",
            assessor_spec=None,
            instrument_version_id=None,
            name=None,
            concurrency=1,
            re_evaluate=False,
        )
        == 0
    )
    study = measured_study(session, generation)
    assert study is not None
    track(cleanup, session, study)

    # Opened, so instrument, judge and dataset are pinned (ADR-0043 §1).
    assert study.status == "open"
    assert study.instrument_version_id == norm
    # The scope is the one version the folder named — a measurement, not a comparison
    # (ADR-0044), and that version is the one the intake registered from the folder name.
    scope = session.execute(
        text(
            "SELECT v.version FROM study_recipe_generators r "
            "JOIN generator_versions v ON v.id = r.generator_version_id WHERE r.study_id = :id"
        ),
        {"id": study.id},
    ).fetchall()
    assert [row.version for row in scope] == ["9c1f2ab-dirty"]
    assert len(no_llm) == 1

    # stdout is ONE json document and nothing else — a caller runs this command and parses
    # what comes back, so a stray line of progress on this stream is a broken contract, not
    # cosmetic noise. Everything the run says about itself goes to stderr.
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert set(document) == {"batch", "fitness"}
    assert document["batch"]["studyId"] == str(study.id)
    assert "created" in captured.err  # the registration reported itself, on the other stream


def test_running_it_again_resumes_the_same_round(
    generation, served, accepted_v2, norm, no_llm, cleanup, session, capsys
):
    kwargs = {
        "root_key": "runs",
        "path": generation,
        "package_format": "LearnpackV2",
        "assessor_spec": None,
        "instrument_version_id": None,
        "name": None,
        "concurrency": 1,
        "re_evaluate": False,
    }
    assert run_measure(**kwargs) == 0
    track(cleanup, session, measured_study(session, generation))
    capsys.readouterr()

    assert run_measure(**kwargs) == 0

    studies = session.execute(
        text("SELECT count(*) FROM studies WHERE name = :n"), {"n": generation}
    ).scalar()
    assert studies == 1, "a second run over the same courses must not declare a second round"
    assert "resuming the open study" in capsys.readouterr().err


# ------------------------------------------------------------------- what it will not guess


def test_an_undeclared_root_is_refused(requires_db, capsys):
    assert run_measure("nope", "x", "LearnpackV2", None, None, None, 1, False) == 1
    assert "LOCAL_SOURCE_ROOTS" in capsys.readouterr().err


def test_a_folder_outside_the_root_is_refused(runs_root, capsys):
    assert run_measure("runs", "../..", "LearnpackV2", None, None, None, 1, False) == 1
    assert "not inside" in capsys.readouterr().err


def test_a_generation_with_no_declared_version_is_refused(runs_root, served, norm, capsys):
    """A round's scope is which versions it measures (ADR-0044). `unknown` declares none, and
    "all of them" is a different statement than the one this folder makes."""
    shutil.copytree(V2_FIXTURES / V2_RUN, runs_root / "unknown" / V2_RUN)

    assert run_measure("runs", "unknown", "LearnpackV2", None, None, None, 1, False) == 1
    assert "declares no generator version" in capsys.readouterr().err


def test_an_unratified_judge_is_refused_before_anything_is_registered(
    generation, served, accepted_v2, norm, capsys, session
):
    """Registering a generation is a fetch per lesson per course and profiles each one. None
    of that is worth doing for a round with nothing to judge it with, so the norm and the
    judge are resolved first — and the store is left as it was."""
    before = session.execute(text("SELECT count(*) FROM contents")).scalar()

    assert (
        run_measure("runs", generation, "LearnpackV2", "drafts-hybrid", None, None, 1, False) == 1
    )

    err = capsys.readouterr().err
    assert "has not ratified" in err
    assert "drafts-structural" in err
    assert session.execute(text("SELECT count(*) FROM contents")).scalar() == before


def test_the_judge_can_be_named_without_its_version(
    generation, served, accepted_v2, norm, no_llm, cleanup, session
):
    """A loop that runs every day should not have to be edited on every bump to keep naming
    the current artifact; `name:version` stays available and is what identifies it."""
    assert (
        run_measure("runs", generation, "LearnpackV2", "drafts-structural", None, None, 1, False)
        == 0
    )
    study = measured_study(session, generation)
    track(cleanup, session, study)
    assert study.status == "open"
