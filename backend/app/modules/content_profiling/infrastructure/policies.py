"""Policy: `ContentVersionRegistered` → profile automatically, behind the acceptance.

The guard chain (13-code-qa §3.4, plus ADR-0029): an adapter must exist for the package
format · its CURRENT version must have an `ExtractionAccepted` act · the coordinates must be
unprofiled · and every artifact locator must be an http(s) URL.

Unprofiled means unprofiled in either state: replaying the event over a content whose profile
exists (ok OR failed) does nothing, so the outbox replay guarantee holds (ADR-0003); retrying
a failed extraction is exclusively the manual path's business.

The locator guard is the price of a fetcher fixed at wiring time (ADR-0029 §2): packages
rooted on a filesystem — the seeder's frozen fixtures, `import-learnpack --base-dir` — are not
reachable from here and stay on the manual path, which picks its own fetcher. It declines
silently rather than failing, because a failure here would commit a sticky `failed` profile
over a package that is perfectly readable. It disappears when the fetcher is resolved from the
package root (ADR-0029 §6).
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

_HTTP_SCHEMES = ("http://", "https://")


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

        contents = RegistryContentGateway(session)
        package = contents.get_package(fact.content_id)
        if package is None:
            return  # deleted between the commit and the dispatch; nothing to profile
        if not all(a.locator.startswith(_HTTP_SCHEMES) for a in package.artifacts):
            # The automatic path fetches over http and only over http: its fetcher is fixed
            # below, at wiring time (ADR-0029 §2). A package rooted on a filesystem — the
            # seeder's frozen fixtures, `import-learnpack --base-dir` — belongs to the manual
            # path, which picks its own.
            #
            # Declining is a no-op ON PURPOSE. Letting the fetch run would commit a `failed`
            # profile, and the guard above refuses existing coordinates in EITHER state, so
            # that row would be stuck on a package that is perfectly readable.
            #
            # `all` over no artifacts is True by design: an artifact-less package has nothing
            # to reach and profiles into all-`absent` entries without touching the network.
            # `any`, or an early return on an empty tuple, would delete that behaviour.
            return

        uow = UnitOfWork(session)
        handler = ProfileContent(
            profiles=profiles,
            contents=contents,
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
