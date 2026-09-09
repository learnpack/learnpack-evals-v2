"""The course session an evaluator's page asks for (ADR-0061).

The provider is a double: what is under test here is the endpoint's own judgement — whose
assignment this is, whether there is anything to embed, and what it answers when the platform
is unreachable. The requests the real adapter builds are covered in
`test_course_seat_provisioning.py`.
"""

import pytest
from conftest import open_campaign_over
from sqlalchemy import text

from app.modules.course_session.application.ports import ExternalSeat, SeatProvisioningFailed
from app.platform import course_session_router

RUBRIC = "learnpack-pedagogical-2.0.0"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


class StubProvider:
    """Answers the four acts without a network. `refusing` makes every act fail."""

    def __init__(self, refusing: str | None = None) -> None:
        self.refusing = refusing

    def _check(self) -> None:
        if self.refusing:
            raise SeatProvisioningFailed(self.refusing)

    def create_seat(self, email: str, display_name: str) -> ExternalSeat:
        self._check()
        return ExternalSeat(provider="breathecode", subject="55", user_id="900")

    def enroll(self, seat: ExternalSeat) -> None:
        self._check()

    def mint_token(self, seat: ExternalSeat) -> str:
        self._check()
        return "tok-live"

    def enable_ai(self, seat: ExternalSeat, token: str) -> None:
        self._check()


@pytest.fixture
def provider(monkeypatch):
    """Patched on the router, which imported the factory by name."""

    def _use(refusing: str | None = None) -> StubProvider:
        stub = StubProvider(refusing)
        monkeypatch.setattr(course_session_router, "get_seat_provider", lambda: stub)
        monkeypatch.setattr(
            course_session_router,
            "get_settings",
            lambda: _settings_with_template(),
        )
        return stub

    return _use


def _settings_with_template():
    from app.config import get_settings

    return get_settings().model_copy(update={"seat_email_template": "seats+{slug}@example.com"})


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    def _make(label: str):
        client = as_user(f"user_{label}_{unique}", f"{label}-{unique}@example.com", label)
        assessor_id = client.get("/me").json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return client, assessor_id

    return _make


@pytest.fixture
def make_content(admin, cleanup, unique):
    def _make(url: str | None = COURSE_URL) -> str:
        body = admin.post(
            "/admin/contents",
            json={
                "package_format": "LearnpackV1",
                "external_id": f"course-{unique}-{url is None}",
                "consumable_url": url,
                "generator_version_id": None,
            },
        ).json()
        cleanup["contents"].append(body["content_id"])
        return body["content_id"]

    return _make


@pytest.fixture
def assign(admin, cleanup):
    def _assign(content_id: str, assessor_id: str) -> str:
        campaign = open_campaign_over(
            admin,
            cleanup,
            [content_id],
            name="Course session campaign",
            instrument_version_id=RUBRIC,
            required_evaluations_per_content=1,
        )
        created = admin.post(
            f"/admin/campaigns/{campaign['campaign_id']}/assignments",
            json={"content_id": content_id, "assessor_id": assessor_id},
        )
        assert created.status_code == 201, created.text
        return created.json()["assignment_id"]

    return _assign


@pytest.fixture
def assign_predating_the_rule(admin, cleanup, session):
    """An assignment over a course with no deployed instance.

    The act refuses to make one now (ADR-0068), and the rows already in the store still have
    to be answered for — so this writes straight to the repository. What it stands for is a
    row from before the rule.
    """

    def _assign(content_id: str, assessor_id: str) -> str:
        from uuid import UUID

        from app.modules.orchestration.domain.assignment import Assignment
        from app.modules.orchestration.infrastructure.repository import (
            SqlAlchemyAssignmentRepository,
        )
        from app.shared.domain.ids import new_id

        campaign = open_campaign_over(
            admin,
            cleanup,
            [content_id],
            name="Course session campaign",
            instrument_version_id=RUBRIC,
            required_evaluations_per_content=1,
        )
        assignment = Assignment(
            id=new_id(),
            campaign_id=UUID(campaign["campaign_id"]),
            content_id=UUID(content_id),
            assessor_id=UUID(assessor_id),
        )
        SqlAlchemyAssignmentRepository(session).add(assignment)
        session.commit()
        return str(assignment.id)

    return _assign


# ---- the session


def test_the_session_travels_in_the_course_url(provider, evaluator, make_content, assign):
    provider()
    client, assessor_id = evaluator("grace")
    assignment_id = assign(make_content(), assessor_id)

    response = client.get(f"/assignments/{assignment_id}/course-session")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["url"] == f"{COURSE_URL}?token=tok-live"
    assert body["ai_session"] is True
    assert body["reason"] is None


def test_a_seat_is_provisioned_once_and_reused(provider, evaluator, make_content, assign, session):
    provider()
    client, assessor_id = evaluator("ada")
    assignment_id = assign(make_content(), assessor_id)

    client.get(f"/assignments/{assignment_id}/course-session")
    client.get(f"/assignments/{assignment_id}/course-session")

    seats = session.execute(
        text("SELECT enrolled_at, ai_enrolled_at FROM course_seats WHERE assessor_id = :id"),
        {"id": assessor_id},
    ).all()
    assert len(seats) == 1
    assert all(stamp is not None for stamp in seats[0])


def test_provisioning_a_seat_reaches_the_outbox_once(
    provider, evaluator, make_content, assign, session
):
    """The fact is that an external identity now exists for this person. Asking for a second
    session is not a second fact."""
    provider()
    client, assessor_id = evaluator("linus")
    assignment_id = assign(make_content(), assessor_id)

    client.get(f"/assignments/{assignment_id}/course-session")
    client.get(f"/assignments/{assignment_id}/course-session")

    published = (
        session.execute(
            text(
                "SELECT event_type FROM events WHERE aggregate_id IN "
                "(SELECT id::text FROM course_seats WHERE assessor_id = :id)"
            ),
            {"id": assessor_id},
        )
        .scalars()
        .all()
    )
    assert published == ["CourseSeatProvisioned"]


# ---- what it answers when there is no session


def test_an_unreachable_platform_still_serves_the_course(provider, evaluator, make_content, assign):
    """The course is readable without its AI. A 5xx would replace a working page."""
    provider(refusing="the platform answered 503")
    client, assessor_id = evaluator("edsger")
    assignment_id = assign(make_content(), assessor_id)

    response = client.get(f"/assignments/{assignment_id}/course-session")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["url"] == COURSE_URL
    assert "token" not in body["url"]
    assert body["ai_session"] is False
    assert body["reason"] == "the platform answered 503"


def test_a_course_with_no_deployed_instance_mints_nothing(
    provider, evaluator, make_content, assign_predating_the_rule
):
    """A different absence from a missing session, and the page says it differently."""
    stub = provider()
    client, assessor_id = evaluator("barbara")
    assignment_id = assign_predating_the_rule(make_content(url=None), assessor_id)

    body = client.get(f"/assignments/{assignment_id}/course-session").json()

    assert body == {"url": None, "ai_session": False, "reason": None}
    # No round trip spent on a page that will show "no deployed instance".
    assert stub.refusing is None


# ---- whose assignment it is


def test_another_evaluator_cannot_open_your_course(provider, evaluator, make_content, assign):
    provider()
    _, mine = evaluator("owner")
    stranger, _ = evaluator("stranger")
    assignment_id = assign(make_content(), mine)

    response = stranger.get(f"/assignments/{assignment_id}/course-session")

    assert response.status_code == 403, response.text


def test_an_unknown_assignment_is_not_found(provider, evaluator):
    provider()
    client, _ = evaluator("grace")

    response = client.get("/assignments/0f1d4e9c-0000-4000-8000-000000000000/course-session")

    assert response.status_code == 404, response.text


def test_a_session_requires_signing_in(provider, as_user):
    """`as_user` installs the claims override; a client that sends no identity through it
    is what an unauthenticated request looks like."""
    from fastapi.testclient import TestClient

    from app.main import app

    provider()
    as_user("someone", "someone@example.com", "Someone")

    response = TestClient(app).get(
        "/assignments/0f1d4e9c-0000-4000-8000-000000000000/course-session"
    )

    assert response.status_code == 401, response.text
