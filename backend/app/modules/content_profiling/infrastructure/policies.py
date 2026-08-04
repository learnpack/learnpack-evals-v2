"""Policy: `ContentVersionRegistered` → profile automatically, behind the acceptance.

The guard chain (13-code-qa §3.4): an adapter must exist for the package format, its
CURRENT version must have an `ExtractionAccepted` act, and the coordinates must be
unprofiled — replaying the event over a content whose profile exists (ok OR failed) does
nothing, so the outbox replay guarantee holds (ADR-0003); retrying a failed extraction is
exclusively the manual path's business.
"""

from app.modules.content_profiling.application.profile_content import (
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import HttpPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.modules.evaluand_registry import public as registry_contract
from app.platform.db import SessionLocal
from app.platform.events import EventDispatcher
from app.platform.uow import UnitOfWork
from app.shared.domain.events import DomainEvent


def on_content_version_registered(event: DomainEvent) -> None:
    # Translate the publisher's contract at the boundary, so the application layer
    # never depends on the Evaluand Registry module.
    fact = registry_contract.ContentVersionRegisteredFact.from_payload(event.payload)

    adapter = ADAPTERS_BY_FORMAT.get(fact.package_format)
    if adapter is None:
        return

    session = SessionLocal()  # a policy runs in its own transaction
    try:
        profiles = SqlAlchemyProfileRepository(session)
        acceptances = SqlAlchemyAcceptanceRepository(session)
        if not acceptances.is_accepted(fact.package_format, adapter.adapter_version):
            return  # profiling stays manual until the human act (ADR-0012)
        if profiles.get_status(fact.content_id, adapter.adapter_version) is not None:
            return  # replay: already recorded, ok or failed
        uow = UnitOfWork(session)
        handler = ProfileContent(
            profiles=profiles,
            contents=RegistryContentGateway(session),
            namespace=DesignNamespaceGateway(session),
            adapters=ADAPTERS_BY_FORMAT,
            fetcher=HttpPackageFetcher(),
            publisher=uow.events,
            uow=uow,
        )
        handler(ProfileContentCommand(content_id=fact.content_id))
    finally:
        session.close()


def register_policies(dispatcher: EventDispatcher) -> None:
    dispatcher.subscribe(
        registry_contract.CONTENT_VERSION_REGISTERED, on_content_version_registered
    )
