"""Use case: declare the deployment of an already-registered content (ADR-0054).

Beside `attribute_generator.py` and shaped like it, with one deliberate difference: this act
**may be repeated**. A generator link is a discovery — the fact was always true and is merely
learnt late — while a deployment is a statement about the world right now, and one that could
be made only once would leave a moved course with a dead link and no repair.

It writes one column and its two record-keeping neighbours. It fetches nothing: a profile is
built from artifact locators and Content Profiling never reads this field (ADR-0028 §4).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.evaluand_registry.application.errors import ContentNotFound
from app.modules.evaluand_registry.application.ports import ContentRepositoryPort
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class ConsumableUrlChangedMeanwhile(Exception):
    """Somebody declared a different URL between the read and the write."""


@dataclass(frozen=True)
class DeclareConsumableUrlCommand:
    content_id: UUID
    consumable_url: str
    declared_by: UUID


class DeclareConsumableUrl:
    def __init__(
        self,
        contents: ContentRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._contents = contents
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: DeclareConsumableUrlCommand) -> EducationalContent:
        content = self._contents.get_by_id(command.content_id)
        if content is None:
            raise ContentNotFound(f"content {command.content_id} is not registered")

        previous = content.consumable_url
        if not content.declare_consumable_url(
            url=command.consumable_url,
            declared_by=command.declared_by,
            at=datetime.now(UTC),
        ):
            # Nothing changed, so nothing is written and nothing is published: an outbox entry
            # that records no change is noise a future reader has to rule out (ADR-0054 §3).
            return content

        if not self._contents.declare_consumable_url(content, previous):
            raise ConsumableUrlChangedMeanwhile(
                f"content {content.id} was declared by someone else first"
            )

        self._publisher.publish(events.consumable_url_declared(content, previous))
        self._uow.commit()
        return content
