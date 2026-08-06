"""Identity domain — pure Python (ARCHITECTURE.md §1).

An `Assessor` is the concrete, identifiable instance that actually produces evaluation
results — the key of provenance and calibration (GLOSSARY.md, Source axis). Two kinds with
a real structural difference (ADR-0016): `human` enters via Clerk/assignments (the
evaluating user *is* an Assessor); `automated` is a versioned software artifact identified
by (name, version) inside `source_config` — it owes itself to an instrument lineage and
declares its coverage per criterion (ADR-0019); it has no external credential.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class Role(StrEnum):
    ADMIN = "admin"
    EVALUATOR = "evaluator"


class Kind(StrEnum):
    HUMAN = "human"
    AUTOMATED = "automated"


class InvalidAssessor(Exception):
    """The assessor breaks an invariant of its aggregate."""


@dataclass
class Assessor:
    """Aggregate root. Identity is `id`; the external credential (`clerk_user_id`) exists
    only for humans; automated assessors carry their identity in `source_config`."""

    id: UUID
    clerk_user_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    role: Role = Role.EVALUATOR
    expertise: str | None = None
    kind: Kind = Kind.HUMAN
    source_config: dict[str, Any] | None = field(default=None)

    def __post_init__(self) -> None:
        # Accepts the raw strings too, so repositories can hydrate straight from the DB.
        if not isinstance(self.role, Role):
            try:
                self.role = Role(self.role)
            except ValueError as exc:
                raise InvalidAssessor(f"unknown role: {self.role!r}") from exc
        if not isinstance(self.kind, Kind):
            try:
                self.kind = Kind(self.kind)
            except ValueError as exc:
                raise InvalidAssessor(f"unknown kind: {self.kind!r}") from exc
        if self.kind is Kind.HUMAN:
            if not self.clerk_user_id or not self.clerk_user_id.strip():
                raise InvalidAssessor("clerk_user_id is required for a human assessor")
        else:
            if self.clerk_user_id is not None:
                raise InvalidAssessor("an automated assessor has no external credential")
            config = self.source_config or {}
            for key in ("name", "version", "instrumentId"):
                if not str(config.get(key, "")).strip():
                    raise InvalidAssessor(
                        f"an automated assessor requires source_config.{key} (ADR-0016/0019)"
                    )

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
