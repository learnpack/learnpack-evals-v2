"""Identity domain — pure Python (ARCHITECTURE.md §1).

An `Assessor` is the concrete, identifiable instance that actually produces evaluation
results — the key of provenance and calibration (GLOSSARY.md, Source axis). In the MVP every
Assessor is of type `HumanExpert`: the evaluating user *is* an Assessor.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    ADMIN = "admin"
    EVALUATOR = "evaluator"


class InvalidAssessor(Exception):
    """The assessor breaks an invariant of its aggregate."""


@dataclass
class Assessor:
    """Aggregate root. Identity is `id`; `clerk_user_id` is the external credential."""

    id: UUID
    clerk_user_id: str
    email: str | None = None
    display_name: str | None = None
    role: Role = Role.EVALUATOR
    expertise: str | None = None

    def __post_init__(self) -> None:
        if not self.clerk_user_id or not self.clerk_user_id.strip():
            raise InvalidAssessor("clerk_user_id is required")
        # Accepts the raw string too, so repositories can hydrate straight from the DB.
        if not isinstance(self.role, Role):
            try:
                self.role = Role(self.role)
            except ValueError as exc:
                raise InvalidAssessor(f"unknown role: {self.role!r}") from exc

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    def assign_role(self, role: Role | str) -> None:
        """Change the role. Only the admin CLI does this — never the login flow."""
        try:
            self.role = Role(role)
        except ValueError as exc:
            raise InvalidAssessor(f"unknown role: {role!r}") from exc

    def update_profile(self, email: str | None, display_name: str | None) -> bool:
        """Refresh the profile from the identity provider. True if anything changed."""
        changed = False
        if email is not None and email != self.email:
            self.email = email
            changed = True
        if display_name is not None and display_name != self.display_name:
            self.display_name = display_name
            changed = True
        return changed
