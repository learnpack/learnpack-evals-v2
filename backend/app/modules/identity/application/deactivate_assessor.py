"""Use case: an assessor leaves, or comes back (ADR-0051).

Just-in-time provisioning covers the arrival and nothing else — nobody stops existing by
not signing in. Without this, an SME who left the project stayed in the assign picker for
ever, and their credential kept opening the door.

Deleting them is not the alternative. An `Assessor` is the key of provenance: their
judgments, the assignments they answered and every report naming them record what happened,
and someone leaving does not unmake it — the argument ADR-0033 already made for content.
So leaving is a **state**, and the two guardrails are the same ones a role change has, for
the same reason: neither failure has an undo inside the product.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.errors import AssessorNotFound, NotAHumanAssessor
from app.modules.identity.application.ports import AssessorRepositoryPort
from app.modules.identity.application.queries import to_dto
from app.modules.identity.domain import events
from app.modules.identity.domain.assessor import Kind
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class CannotDeactivateYourself(Exception):
    """One click from locking yourself out, while meaning to tidy a list."""


class CannotDeactivateLastAdmin(Exception):
    """Deactivating them leaves nobody who can administer, and no screen that could
    bring them back."""


@dataclass(frozen=True)
class SetAssessorActiveCommand:
    assessor_id: UUID
    active: bool
    changed_by: UUID


class SetAssessorActive:
    """Deactivate or reactivate. One use case rather than two, because the refusals belong
    to the transition and stating them twice is how the two drift apart."""

    def __init__(
        self,
        assessors: AssessorRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._assessors = assessors
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: SetAssessorActiveCommand) -> AssessorDTO:
        assessor = self._assessors.get_by_id(command.assessor_id)
        if assessor is None:
            raise AssessorNotFound(str(command.assessor_id))
        if assessor.kind is not Kind.HUMAN:
            raise NotAHumanAssessor(str(command.assessor_id))
        if assessor.is_active is command.active:
            # Nothing happened, so nothing is reported (the rule ADR-0050 §3 set).
            return to_dto(assessor)

        if not command.active:
            if assessor.id == command.changed_by:
                raise CannotDeactivateYourself(str(command.assessor_id))
            if assessor.is_admin and self._assessors.count_admins() <= 1:
                raise CannotDeactivateLastAdmin(str(command.assessor_id))
            assessor.deactivate()
            event = events.assessor_deactivated(assessor, command.changed_by)
        else:
            assessor.reactivate()
            event = events.assessor_reactivated(assessor, command.changed_by)

        self._assessors.update(assessor)
        self._publisher.publish(event)
        self._uow.commit()
        return to_dto(assessor)
