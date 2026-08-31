"""Use case: keep the name a package declares, for a course registered before it was kept
(ADR-0059).

This is the shape of `attribute_generator` with the act taken out of it. The rule is the
same and stated twice for the same reason — the aggregate says it where it is read, the
repository's `WHERE title IS NULL` holds it under concurrency — but there is no author, no
timestamp and no event, because nothing about the content changed. The row is catching up
with what its package always said.

The title arrives as a string. Where the caller read it is the caller's business: today it
is the `course_descriptor` of the profile that same package produced, which is the only
place the value survives for a course registered before the column existed.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluand_registry.application.errors import ContentNotFound
from app.modules.evaluand_registry.application.ports import ContentRepositoryPort
from app.modules.evaluand_registry.domain.content import (
    EducationalContent,
    TitleAlreadyRecorded,
)
from app.shared.application.ports import UnitOfWorkPort


@dataclass(frozen=True)
class RecordContentTitleCommand:
    content_id: UUID
    title: str


class RecordContentTitle:
    def __init__(self, contents: ContentRepositoryPort, uow: UnitOfWorkPort) -> None:
        self._contents = contents
        self._uow = uow

    def __call__(self, command: RecordContentTitleCommand) -> EducationalContent:
        content = self._contents.get_by_id(command.content_id)
        if content is None:
            raise ContentNotFound(f"content {command.content_id} is not registered")

        content.record_discovered_title(command.title)
        if not self._contents.record_title(content):
            raise TitleAlreadyRecorded(f"content {content.id} was named by someone else first")

        self._uow.commit()
        return content
