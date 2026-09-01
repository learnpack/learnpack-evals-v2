"""Provisioning a course seat (ADR-0061).

No database and no network: the provider's requests are built for real and answered by a
mock transport, and the use cases run against in-memory doubles. What is under test is the
part that is easy to get wrong and expensive to discover in production — that an interrupted
provisioning resumes instead of restarting, and that a provider outage degrades instead of
taking the page down.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest

from app.config import get_settings
from app.modules.course_session.application.ensure_seat import (
    EnsureCourseSeat,
    EnsureCourseSeatCommand,
    seat_email,
)
from app.modules.course_session.application.mint_session import (
    MintCourseSession,
    MintCourseSessionCommand,
)
from app.modules.course_session.application.ports import (
    ExternalSeat,
    SeatProvisioningFailed,
)
from app.modules.course_session.domain.seat import CourseSeat, SeatStatus
from app.modules.course_session.infrastructure import providers

TEMPLATE = "seats+sme-{slug}@example.com"


# ---- doubles


class FakeSeatRepository:
    def __init__(self, seat: CourseSeat | None = None) -> None:
        self.seat = seat
        self.updates = 0

    def get_by_assessor(self, assessor_id: UUID) -> CourseSeat | None:
        return self.seat

    def add(self, seat: CourseSeat) -> None:
        seat.created_at = datetime.now(UTC)
        self.seat = seat

    def update(self, seat: CourseSeat) -> None:
        self.updates += 1
        self.seat = seat


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:  # pragma: no cover — never reached in these tests
        raise AssertionError("rollback is not part of provisioning")


class FakeProvider:
    """Records the acts, and can be told to fail at one of them."""

    def __init__(self, fail_at: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_at = fail_at

    def _act(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            raise SeatProvisioningFailed(f"{name} refused")

    def create_seat(self, email: str, display_name: str) -> ExternalSeat:
        self._act("create_seat")
        return ExternalSeat(provider="breathecode", subject="55", user_id="900")

    def enroll(self, seat: ExternalSeat) -> None:
        self._act("enroll")

    def mint_token(self, seat: ExternalSeat) -> str:
        self._act("mint_token")
        return "tok-live"

    def enable_ai(self, seat: ExternalSeat, token: str) -> None:
        self._act("enable_ai")


def make_seat(**overrides: object) -> CourseSeat:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "assessor_id": uuid4(),
        "provider": "breathecode",
        "external_subject": "55",
        "external_user_id": "900",
        "email": "seats+sme-abc@example.com",
    }
    return CourseSeat(**(defaults | overrides))  # type: ignore[arg-type]


def ensure(repo: FakeSeatRepository, provider: FakeProvider) -> tuple[EnsureCourseSeat, FakeUow]:
    uow = FakeUow()
    return (
        EnsureCourseSeat(
            seats=repo,
            provider=provider,
            publisher=FakePublisher(),
            uow=uow,
            email_template=TEMPLATE,
        ),
        uow,
    )


# ---- the seat's address


def test_the_address_is_derived_from_the_assessor_not_the_person() -> None:
    assessor = UUID("1a2b3c4d-0000-0000-0000-000000000000")
    assert seat_email(TEMPLATE, assessor) == "seats+sme-1a2b3c4d@example.com"


def test_two_assessors_never_share_an_address() -> None:
    assert seat_email(TEMPLATE, uuid4()) != seat_email(TEMPLATE, uuid4())


@pytest.mark.parametrize("template", ["", "   ", "seats@example.com"])
def test_a_template_that_cannot_distinguish_seats_is_refused(template: str) -> None:
    """A template without `{slug}` would hand every assessor one address, and the second
    seat would fail with a duplicate error that reads like a provider bug."""
    with pytest.raises(SeatProvisioningFailed):
        seat_email(template, uuid4())


# ---- provisioning resumes, it does not restart


def test_a_new_seat_runs_every_act_once() -> None:
    provider = FakeProvider()
    use_case, uow = ensure(FakeSeatRepository(), provider)

    seat = use_case(EnsureCourseSeatCommand(assessor_id=uuid4()))

    assert provider.calls == ["create_seat", "enroll", "mint_token", "enable_ai"]
    assert seat.is_ready
    # One per external step that succeeded: the row is durable before the next call runs.
    assert uow.commits == 3


def test_a_seat_created_but_never_enrolled_is_finished_not_recreated() -> None:
    """The failure this whole design exists for: the identity is already taken over there,
    so asking for it again is refused and the seat would be unreachable for ever."""
    provider = FakeProvider()
    repo = FakeSeatRepository(make_seat())
    use_case, _ = ensure(repo, provider)

    seat = use_case(EnsureCourseSeatCommand(assessor_id=uuid4()))

    assert "create_seat" not in provider.calls
    assert provider.calls == ["enroll", "mint_token", "enable_ai"]
    assert seat.is_ready


def test_a_ready_seat_touches_neither_the_provider_nor_the_store() -> None:
    now = datetime.now(UTC)
    repo = FakeSeatRepository(make_seat(enrolled_at=now, ai_enrolled_at=now))
    provider = FakeProvider()
    use_case, uow = ensure(repo, provider)

    use_case(EnsureCourseSeatCommand(assessor_id=uuid4()))

    assert provider.calls == []
    assert repo.updates == 0
    assert uow.commits == 0


def test_the_seat_survives_a_failure_halfway_through() -> None:
    repo = FakeSeatRepository()
    use_case, _ = ensure(repo, FakeProvider(fail_at="enroll"))

    with pytest.raises(SeatProvisioningFailed):
        use_case(EnsureCourseSeatCommand(assessor_id=uuid4()))

    # The row exists, so the next attempt resumes instead of asking for a taken address.
    assert repo.seat is not None
    assert repo.seat.enrolled_at is None


def test_a_revoked_seat_is_not_quietly_reused() -> None:
    repo = FakeSeatRepository(make_seat(status=SeatStatus.REVOKED))
    use_case, _ = ensure(repo, FakeProvider())

    with pytest.raises(SeatProvisioningFailed, match="revoked"):
        use_case(EnsureCourseSeatCommand(assessor_id=uuid4()))


# ---- minting answers instead of raising


def test_a_session_carries_the_token_when_everything_works() -> None:
    provider = FakeProvider()
    use_case, _ = ensure(FakeSeatRepository(), provider)

    session = MintCourseSession(use_case, provider)(MintCourseSessionCommand(assessor_id=uuid4()))

    assert session.granted
    assert session.token == "tok-live"
    assert session.reason is None


def test_a_provider_outage_becomes_an_answer_not_an_error() -> None:
    """The course is still readable without AI. A 500 would replace a working page."""
    provider = FakeProvider(fail_at="create_seat")
    use_case, _ = ensure(FakeSeatRepository(), provider)

    session = MintCourseSession(use_case, provider)(MintCourseSessionCommand(assessor_id=uuid4()))

    assert not session.granted
    assert session.token is None
    assert session.reason == "create_seat refused"


# ---- the requests the adapter actually builds


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201 — pytest fixture
    sent: list[httpx.Request] = []

    def _platform(status_code: int = 200, body: object | None = None):  # noqa: ANN202
        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return httpx.Response(
                status_code, json=body if body is not None else {"id": 55, "user": {"id": 900}}
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(
            providers.httpx, "post", lambda url, **kwargs: client.post(url, **kwargs)
        )
        return sent

    return _platform


def provider_under_test() -> providers.BreatheCodeSeatProvider:
    return providers.BreatheCodeSeatProvider(
        api_url="https://bc.example.com/",
        service_token="svc-token",
        academy_id="92",
        cohort_id="7",
        ai_api_url="https://ai.example.com",
        ai_organization="learnpack",
    )


def test_creating_a_seat_names_the_academy_and_asks_for_an_invite(platform) -> None:  # noqa: ANN001
    sent = platform()

    seat = provider_under_test().create_seat("seats+sme-abc@example.com", "SME Seat abc")

    assert seat == ExternalSeat(provider="breathecode", subject="55", user_id="900")
    request = sent[0]
    assert request.url.path == "/v1/auth/academy/student"
    assert request.headers["authorization"] == "Token svc-token"
    assert request.headers["academy"] == "92"
    assert _json(request)["invite"] is True


def test_a_seat_without_an_account_id_says_what_it_did_create(platform) -> None:  # noqa: ANN001
    """Naming the membership matters: it exists over there, and an operator has to find it."""
    platform(body={"id": 55})

    with pytest.raises(SeatProvisioningFailed, match="membership=55"):
        provider_under_test().create_seat("seats+sme-abc@example.com", "SME Seat abc")


def test_enrolling_sends_the_account_id_as_an_integer(platform) -> None:  # noqa: ANN001
    """The platform validates the type and refuses a string."""
    sent = platform(body={})

    provider_under_test().enroll(ExternalSeat("breathecode", "55", "900"))

    body = _json(sent[0])
    assert sent[0].url.path == "/v1/admissions/academy/cohort/7/user"
    assert body["user"] == 900
    assert body["educational_status"] == "ACTIVE"
    assert "finantial_status" not in body


def test_minting_returns_the_key(platform) -> None:  # noqa: ANN001
    sent = platform(body={"key": "tok-live"})

    token = provider_under_test().mint_token(ExternalSeat("breathecode", "55", "900"))

    assert token == "tok-live"
    assert sent[0].url.path == "/v1/auth/member/55/token"


def test_registering_with_the_ai_service_carries_the_token_not_our_credential(platform) -> None:  # noqa: ANN001
    sent = platform(body={})

    provider_under_test().enable_ai(ExternalSeat("breathecode", "55", "900"), "tok-live")

    request = sent[0]
    assert request.url.path == "/v2/auth/invite"
    assert "authorization" not in request.headers
    assert _json(request) == {"organization": "learnpack", "user_token": "tok-live"}


def test_a_refusal_carries_the_platforms_own_sentence(platform) -> None:  # noqa: ANN001
    platform(status_code=403, body={"detail": "This academy is not active"})

    with pytest.raises(SeatProvisioningFailed, match="This academy is not active"):
        provider_under_test().create_seat("seats+sme-abc@example.com", "SME Seat abc")


def test_an_unreachable_platform_is_a_provisioning_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(url: str, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(providers.httpx, "post", explode)

    with pytest.raises(SeatProvisioningFailed, match="could not create the seat"):
        provider_under_test().create_seat("seats+sme-abc@example.com", "SME Seat abc")


# ---- which adapter runs


def test_local_mode_mints_nothing_and_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    _as_settings(monkeypatch, auth_mode="local")
    provider = providers.get_seat_provider()

    assert isinstance(provider, providers.UnconfiguredSeatProvider)
    with pytest.raises(SeatProvisioningFailed, match="AUTH_MODE=local"):
        provider.mint_token(ExternalSeat("breathecode", "55", "900"))


def test_missing_credentials_name_themselves(monkeypatch: pytest.MonkeyPatch) -> None:
    _as_settings(monkeypatch, auth_mode="clerk", breathecode_service_token="svc")
    provider = providers.get_seat_provider()

    assert isinstance(provider, providers.UnconfiguredSeatProvider)
    with pytest.raises(SeatProvisioningFailed, match="BREATHECODE_ACADEMY_ID"):
        provider.mint_token(ExternalSeat("breathecode", "55", "900"))


def test_a_configured_deployment_talks_to_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    _as_settings(
        monkeypatch,
        auth_mode="clerk",
        breathecode_service_token="svc",
        breathecode_academy_id="92",
        breathecode_cohort_id="7",
    )
    assert isinstance(providers.get_seat_provider(), providers.BreatheCodeSeatProvider)


# ---- helpers


def _json(request: httpx.Request) -> dict:
    import json

    return json.loads(request.content)


def _as_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    settings = get_settings().model_copy(update=overrides)
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
