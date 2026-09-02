import json
import os
import pathlib
import re
import uuid
from collections.abc import Iterator

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings

INSTRUMENTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "docs" / "seed" / "instruments"

# One authored instrument, for tests that need a whole spec to copy and mutate. The declared
# namespace below is NOT read from here: ids are global across instruments (ADR-0014), so
# reading one file would hide every id another instrument mints.
INSTRUMENT_SPEC_FILE = INSTRUMENTS_DIR / "learnpack-course-qa-v1.yaml"

# The drafts lineage's current version — what `drafts-structural` declares coverage over.
DRAFTS_INSTRUMENT_SPEC_FILE = INSTRUMENTS_DIR / "course-drafts-qa-v9.yaml"


def declared_value_domains() -> dict[str, dict]:
    """The declared demand-side namespace (ADR-0020), merged across every authored
    instrument. Tests mint it from the real files rather than from a copy, so a profiling
    fixture can never pass against a shape no instrument declares.

    Two files declaring one id with different shapes is refused here, loudly. The DB is
    already guarded — the import lint blocks a divergent redeclaration — but that guard only
    fires when someone imports, and these files are read straight off disk.
    """
    domains: dict[str, dict] = {}
    declared_by: dict[str, str] = {}
    for spec_file in sorted(INSTRUMENTS_DIR.glob("*.yaml")):
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        for requirement in spec.get("data_requirements", []):
            requirement_id, domain = requirement["id"], requirement["value_domain"]
            if domains.get(requirement_id, domain) != domain:
                raise AssertionError(
                    f"data requirement '{requirement_id}' is declared with two different "
                    f"value domains: {declared_by[requirement_id]} says "
                    f"{json.dumps(domains[requirement_id], sort_keys=True)}, {spec_file.name} "
                    f"says {json.dumps(domain, sort_keys=True)} — one id, one shape (ADR-0020)"
                )
            domains[requirement_id] = domain
            declared_by[requirement_id] = spec_file.name
    return domains


LEARNPACK_FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "learnpack_v1"


def fixture_artifact_rows(course: str) -> list[dict]:
    """A frozen package's declared surface, discovered mechanically (ADR-0027), with
    locators relative to the fixtures dir — what registration-needing tests pass as
    `artifacts` and the filesystem fetchers then resolve."""
    from app.modules.evaluand_registry.infrastructure.package_discovery import (
        FilesystemPackageRoot,
        LearnpackV1Discovery,
    )

    discovered = LearnpackV1Discovery().discover(
        FilesystemPackageRoot(LEARNPACK_FIXTURES / course, locator_base=course)
    )
    return [
        {"kind": a.kind, "locator": a.locator, "format": a.format} for a in discovered.artifacts
    ]


@pytest.fixture
def namespace(cleanup):
    """Mint the canonical demand-side namespace extraction adapters conform to.

    Normally the instrument import's job (ADR-0014). Ids and value domains both come from
    the shipped instrument, so what an adapter produces in a test is checked against the
    shape the team actually declared — not against a copy that can drift.
    """
    from app.platform.db import SessionLocal

    with SessionLocal() as session:
        for requirement_id, domain in declared_value_domains().items():
            session.execute(
                text(
                    "INSERT INTO data_requirements (id, definition, value_domain) "
                    "VALUES (:id, :definition, cast(:value_domain as jsonb)) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": requirement_id,
                    "definition": f"test definition of {requirement_id}",
                    "value_domain": json.dumps(domain),
                },
            )
            cleanup["data_requirements"].append(requirement_id)
        session.commit()


@pytest.fixture
def accepted_extraction(cleanup):
    """Arm auto-profiling for the CURRENT LearnpackV1 adapter (ADR-0012's human act).

    Lives here rather than in one test file because the row is **global**: it arms the policy
    for every content registered afterwards, through any path, for the rest of the session.
    Registering it in `cleanup` is therefore mandatory (see that fixture's docstring), and a
    single shared fixture is the only way to make forgetting impossible — a leak breaks
    `test_profiling_api`'s `accepted is False`, and the failure points at the wrong file.
    """
    from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
    from app.platform.db import SessionLocal

    adapter = ADAPTERS_BY_FORMAT["LearnpackV1"]
    cleanup["acceptances"].append(("LearnpackV1", adapter.adapter_version))
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO extraction_acceptances (package_format, adapter_version, accepted_by)"
                " VALUES ('LearnpackV1', :version, :by) ON CONFLICT DO NOTHING"
            ),
            {"version": adapter.adapter_version, "by": uuid.uuid4()},
        )
        session.commit()


# --- where the suite runs -------------------------------------------------------------
# Redirected at import time, before anything can build an engine. With TEST_DATABASE_URL
# pointing at the local Postgres (docker-compose.yml), the suite runs ~500x faster: it is
# latency-bound, and Neon is ~150 ms per round trip from here versus ~0.3 ms locally.
_TEST_URL = get_settings().test_database_url
USING_LOCAL_TEST_DB = bool(_TEST_URL)

if USING_LOCAL_TEST_DB:
    # An env var outranks the .env file in pydantic-settings, so this wins.
    os.environ["DATABASE_URL"] = _TEST_URL
    get_settings.cache_clear()

# The suite writes no trace files. `LLM_TRACE_DIR` is a developer's folder for reading what
# the real model was asked, and a fake attempt from a test is indistinguishable from a real
# one once it is sitting there next to them — the run id in the filename says nothing about
# who wrote it. What writes those files is pinned directly, against `tmp_path`, in
# `test_preview_runs.py`.
os.environ["LLM_TRACE_DIR"] = ""
get_settings.cache_clear()


def _explain_unreachable_database(error: Exception) -> str:
    """Turn a connection failure into the remedy, because the default reading is wrong.

    Three states, three remedies — and the middle one is the reason this exists. A wrong
    server on the right port answers and REFUSES, so the suite reports an authentication
    problem, which sends a reader looking for a bad password. Nothing is wrong with the
    password: they reached somebody else's Postgres. It has happened twice.
    """
    detail = str(error)
    # The host and port are the whole diagnosis; the credentials are not, and a password is
    # not a thing to print to a terminal even when it is `postgres`.
    where = f"`{re.sub(r'//[^@/]*@', '//', _TEST_URL or '')}`"

    if "password authentication failed" in detail:
        return (
            f"Something is listening on that port and it is NOT this repo's container: it "
            f"answered and refused the credentials ({where}).\n\n"
            "The usual cause is a Postgres installed natively on this machine. Its installer "
            "assigns 5432 to the first instance and scans upward for the next, so a second "
            "one lands near it; published container ports in that neighbourhood get shadowed, "
            "and `localhost` reaches the native server. Stop that service, or move it.\n\n"
            "Note that a refused connection would mean nothing is there. This is the opposite: "
            "somebody answered."
        )
    # A refused connection and a timeout are one state with one remedy. Windows usually
    # produces the timeout — which is also why this takes a while to arrive.
    if any(
        symptom in detail
        for symptom in ("Connection refused", "connection refused", "could not connect", "timeout")
    ):
        return (
            f"Nothing is listening at {where}.\n\n"
            "Run `docker compose up -d` in `backend/`. The suite needs the local Postgres; it "
            "errors rather than skipping, on purpose — a green run that silently tested "
            "nothing is worse than a red one."
        )
    return f"The test database at {where} could not be reached.\n\n{detail}"


def declare_dataset_over(admin, cleanup, content_ids, name="a campaign under test"):
    """A dataset over these courses, tracked for cleanup, returning its version id.

    Its own helper because the tests that check a campaign is *refused* still need a version
    the store can resolve — otherwise they would pass for the wrong reason.
    """
    declared = admin.post(
        "/admin/datasets",
        json={
            "name": f"Set for {name}",
            "note": "the courses this test runs on",
            "content_ids": list(content_ids),
        },
    )
    assert declared.status_code == 201, declared.text
    dataset = declared.json()
    cleanup["datasets"].append(dataset["dataset_id"])
    return dataset["versions"][-1]["version_id"]


def open_campaign_over(admin, cleanup, content_ids, **overrides):
    """Declare a dataset over these courses and open a campaign against its version.

    A campaign's scope is **named, not listed** (ADR-0058 §5), so opening one is two acts.
    One helper rather than the same six lines in six files — and it returns the campaign body
    whole, because half the callers want the id and half want a field off it.

    `overrides` go to the campaign; everything about the set is this helper's business,
    since no test is about how the set was named.
    """
    version_id = declare_dataset_over(
        admin, cleanup, content_ids, overrides.get("name", "a campaign under test")
    )

    payload = {
        "name": "Campaign under test",
        "instrument_version_id": "learnpack-pedagogical-2.0.0",
        "required_evaluations_per_content": 1,
        "dataset_version_id": version_id,
    } | overrides
    opened = admin.post("/admin/campaigns", json=payload)
    assert opened.status_code == 201, opened.text
    campaign = opened.json()
    cleanup["campaigns"].append(campaign["campaign_id"])
    return campaign


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> None:
    """Bring the local test database up to date once per session.

    Deliberately a no-op against Neon: migrating and seeding automatically is fine for a
    throwaway container, not for the real store.
    """
    if not USING_LOCAL_TEST_DB:
        return

    from alembic.config import Config
    from sqlalchemy.exc import OperationalError

    from alembic import command
    from app.cli import DEFAULT_SEED_FILE, run_seed

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(root, "alembic"))
    try:
        command.upgrade(config, "head")
        run_seed(DEFAULT_SEED_FILE)
    except OperationalError as error:
        # Stop at the door rather than letting every test fail with the same stack: nine
        # hundred identical tracebacks bury the one line that says what to do.
        pytest.exit(
            f"\n\nThe test database is unreachable.\n\n{_explain_unreachable_database(error)}\n",
            returncode=1,
        )


@pytest.fixture(scope="session")
def requires_db() -> None:
    """Skip tests that need a real database when none is configured."""
    if not get_settings().database_url:
        pytest.skip("neither TEST_DATABASE_URL nor DATABASE_URL is set")


@pytest.fixture
def session(requires_db):
    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        yield s


@pytest.fixture
def unique() -> str:
    """A per-test suffix, so runs against the shared Neon never collide."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def register_generator_version(cleanup):
    """Mint a lineage and one version under it, tracked for cleanup, and return the **version**
    id — which is what a content declares.

    One call, because almost every test wants "a registered examinee" rather than the two acts
    that produce it (ADR-0031). Tests that are *about* those acts call them directly.
    """
    from app.modules.evaluand_registry.application.register_generator import (
        RegisterGenerator,
        RegisterGeneratorCommand,
    )
    from app.modules.evaluand_registry.application.register_generator_version import (
        RegisterGeneratorVersion,
        RegisterGeneratorVersionCommand,
    )
    from app.modules.evaluand_registry.infrastructure.repository import (
        SqlAlchemyGeneratorRepository,
        SqlAlchemyGeneratorVersionRepository,
    )
    from app.platform.db import SessionLocal
    from app.platform.uow import UnitOfWork

    def _register(name: str, version: str = "1.0.0", metadata: dict | None = None):
        with SessionLocal() as s:
            generators = SqlAlchemyGeneratorRepository(s)
            uow = UnitOfWork(s)
            generator = RegisterGenerator(generators, uow.events, uow)(
                RegisterGeneratorCommand(name=name)
            )
            cleanup["generator_lineages"].append(generator.id)

            uow = UnitOfWork(s)
            registered = RegisterGeneratorVersion(
                generators, SqlAlchemyGeneratorVersionRepository(s), uow.events, uow
            )(
                RegisterGeneratorVersionCommand(
                    generator_id=generator.id, version=version, metadata=metadata or {}
                )
            )
            cleanup["generators"].append(registered.id)
            return registered.id

    return _register


@pytest.fixture
def cleanup(requires_db) -> Iterator[dict[str, list]]:
    """Collect rows created by a test and remove them afterwards.

    Deletion follows the FK order: studies → datasets → evaluations/completions → assignments →
    campaigns → profiles → contents → generators/briefs → generator lineages → invitations →
    assessors.
    Outbox rows are
    keyed by the aggregate id that produced them. `acceptances` holds (package_format,
    adapter_version) tuples — an acceptance is global, so any test that creates one MUST
    register it here or every later content registration in the session would get auto-profiled.

    `generators` holds generator **version** ids and `generator_lineages` the ids of the
    `Generator` rows that own them (ADR-0031) — two buckets because they are two tables with a
    foreign key between them.
    """
    created: dict[str, list] = {
        "contents": [],
        "assessors": [],
        "invitations": [],
        "campaigns": [],
        "generators": [],
        "generator_lineages": [],
        "briefs": [],
        "instruments": [],
        "data_requirements": [],
        "acceptances": [],
        "studies": [],
        "datasets": [],
    }
    yield created

    from app.platform.db import SessionLocal

    with SessionLocal() as s:
        # Studies first: they reference contents and instruments (no FK, but the rows
        # would go stale). Recipe/dataset/report cascade with the study row.
        for study_id in created["studies"]:
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(study_id)})
            s.execute(text("DELETE FROM studies WHERE id = :id"), {"id": study_id})

        # Datasets before contents: their members reference contents with no FK, so nothing
        # would stop the rows going stale. Versions and members cascade with the dataset row.
        for dataset_id in created["datasets"]:
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(dataset_id)})
            s.execute(text("DELETE FROM datasets WHERE id = :id"), {"id": dataset_id})

        for content_id in created["contents"]:
            s.execute(
                text(
                    "DELETE FROM item_scores WHERE evaluation_id IN "
                    "(SELECT id FROM evaluations WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            # Judgment outbox rows are keyed by the judgment id (QualityJudgmentPublished
            # + FindingRaised share the aggregate); the judgment/claim/finding/outcome/
            # metric rows themselves cascade with the evaluations delete below.
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM quality_judgments WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM evaluations WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            s.execute(text("DELETE FROM evaluations WHERE content_id = :id"), {"id": content_id})

        for campaign_id in created["campaigns"]:
            s.execute(
                text("DELETE FROM golden_references WHERE campaign_id = :id"), {"id": campaign_id}
            )
            s.execute(
                text("DELETE FROM content_evaluation_completions WHERE campaign_id = :id"),
                {"id": campaign_id},
            )
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM assignments WHERE campaign_id = :id)"
                ),
                {"id": campaign_id},
            )
            s.execute(text("DELETE FROM assignments WHERE campaign_id = :id"), {"id": campaign_id})
            s.execute(
                text("DELETE FROM campaign_contents WHERE campaign_id = :id"), {"id": campaign_id}
            )
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(campaign_id)})
            s.execute(text("DELETE FROM campaigns WHERE id = :id"), {"id": campaign_id})

        for content_id in created["contents"]:
            # Profiles (and their outbox rows) go before the content they reference;
            # entries/extras cascade with the profile row.
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM content_profiles WHERE content_id = :id)"
                ),
                {"id": content_id},
            )
            s.execute(
                text("DELETE FROM content_profiles WHERE content_id = :id"), {"id": content_id}
            )
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(content_id)})
            # content_package_artifacts cascade with the content row.
            s.execute(text("DELETE FROM contents WHERE id = :id"), {"id": content_id})
        # Generators and briefs go after contents, which reference them.
        for generator_id in created["generators"]:
            s.execute(
                text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(generator_id)}
            )
            s.execute(text("DELETE FROM generator_versions WHERE id = :id"), {"id": generator_id})
        # And the lineage after its versions, which reference it (ADR-0031).
        for lineage_id in created["generator_lineages"]:
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(lineage_id)})
            s.execute(text("DELETE FROM generators WHERE id = :id"), {"id": lineage_id})
        for brief_id in created["briefs"]:
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(brief_id)})
            s.execute(text("DELETE FROM generation_briefs WHERE id = :id"), {"id": brief_id})
        for instrument_id in created["instruments"]:
            # Children go with the row (ON DELETE CASCADE).
            s.execute(text("DELETE FROM events WHERE aggregate_id = :id"), {"id": instrument_id})
            s.execute(text("DELETE FROM instrument_versions WHERE id = :id"), {"id": instrument_id})
        for requirement_id in created["data_requirements"]:
            s.execute(text("DELETE FROM data_requirements WHERE id = :id"), {"id": requirement_id})
        for package_format, adapter_version in created["acceptances"]:
            s.execute(
                text("DELETE FROM events WHERE aggregate_id = :id"),
                {"id": f"{package_format}:{adapter_version}"},
            )
            s.execute(
                text(
                    "DELETE FROM extraction_acceptances "
                    "WHERE package_format = :f AND adapter_version = :v"
                ),
                {"f": package_format, "v": adapter_version},
            )
        # Before the assessors: an invitation references the admin who sent it and the
        # assessor it produced, and its outbox rows are keyed by its own id.
        for invitation_id in created["invitations"]:
            s.execute(
                text("DELETE FROM events WHERE aggregate_id = :id"), {"id": str(invitation_id)}
            )
            s.execute(
                text("DELETE FROM assessor_invitations WHERE id = :id"), {"id": invitation_id}
            )

        for assessor_id in created["assessors"]:
            # A course seat has no bucket of its own because no test creates one: it appears
            # when an evaluator opens a course, keyed by the assessor, so it is deleted with
            # them. Its outbox rows are keyed by the seat's id, which only the row knows.
            s.execute(
                text(
                    "DELETE FROM events WHERE aggregate_id IN "
                    "(SELECT id::text FROM course_seats WHERE assessor_id = :id)"
                ),
                {"id": assessor_id},
            )
            s.execute(text("DELETE FROM course_seats WHERE assessor_id = :id"), {"id": assessor_id})
            # Ratifications usually cascade with the tracked instrument versions above;
            # this covers the assessor-as-ratifier side (ratified_by has no cascade).
            s.execute(
                text(
                    "DELETE FROM assessor_ratifications "
                    "WHERE assessor_id = :id OR ratified_by = :id"
                ),
                {"id": assessor_id},
            )
            s.execute(text("DELETE FROM assessors WHERE id = :id"), {"id": assessor_id})
        s.commit()


@pytest.fixture
def as_user(requires_db, cleanup):
    """A TestClient authenticated as a given Clerk identity.

    Only `get_verified_claims` is overridden — the signature check is covered by
    tests/test_clerk_jwt.py. Everything downstream (ResolveAssessor, require_admin) is the
    real thing, which is the point: this exercises the authorisation chain.

    The identity is resolved **per request**, from a test-only header. A single shared
    override keyed on the client would be wrong: several clients (an admin and two
    evaluators) are alive at the same time in the flow tests.
    """
    from fastapi import HTTPException, Request

    from app.main import app
    from app.platform.security import get_verified_claims

    identities: dict[str, dict] = {}

    def _override(request: Request) -> dict:
        claims = identities.get(request.headers.get("x-test-identity", ""))
        if claims is None:
            raise HTTPException(status_code=401, detail="missing bearer token")
        return claims

    app.dependency_overrides[get_verified_claims] = _override

    def _client(
        subject: str,
        email: str | None = None,
        name: str | None = None,
        email_verified: bool = True,
    ):
        # Verified by default: that is what a real session carries, and the unverified case
        # is a deliberate scenario a test opts into (ADR-0049).
        identities[subject] = {
            "sub": subject,
            "email": email,
            "name": name,
            "email_verified": email_verified,
        }
        return TestClient(app, headers={"X-Test-Identity": subject})

    yield _client
    app.dependency_overrides.clear()


@pytest.fixture
def promote(session):
    """Give an assessor the admin role, the way the CLI does."""

    def _promote(email: str) -> None:
        session.execute(
            text("UPDATE assessors SET role = 'admin' WHERE lower(email) = lower(:e)"),
            {"e": email},
        )
        session.commit()

    return _promote


@pytest.fixture
def register_assessor(session, cleanup, as_user):
    """Sign a user in once (creating the Assessor) and return their id."""

    def _register(subject: str, email: str, name: str = "Test User"):
        client = as_user(subject, email, name)
        response = client.get("/me")
        assert response.status_code == 200, response.text
        assessor_id = response.json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return assessor_id

    return _register


@pytest.fixture
def course_server(tmp_path):
    """A live copy of the frozen bare course, served over real http on an ephemeral port —
    so discovery, hashing and `consumable_url` all ride the actual transport, which is
    what the http intake paths are about. The files stay writable, so a test can mutate
    the course between registrations, and the served root is `tmp_path`, so a test can
    put more courses beside it."""
    import functools
    import http.server
    import pathlib
    import shutil
    import threading

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "learnpack_v1"
    course_dir = tmp_path / "bare-course"
    shutil.copytree(fixtures / "bare-course", course_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # keep 404 probes out of the test output
            pass

    handler = functools.partial(QuietHandler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", course_dir
    server.shutdown()
