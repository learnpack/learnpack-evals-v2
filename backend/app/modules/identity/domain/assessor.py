"""Identity domain — pure Python (ARCHITECTURE.md §1).

An `Assessor` is the concrete, identifiable instance that actually produces evaluation
results — the key of provenance and calibration (GLOSSARY.md, Source axis). Two kinds with
a real structural difference (ADR-0016): `human` arrives with an external credential and is
assigned work (the evaluating user *is* an Assessor); `automated` is a versioned software
artifact identified by (name, version) inside `source_config` — it owes itself to an
instrument lineage and declares its coverage per criterion (ADR-0019); it has no external
credential.

The credential is `(auth_provider, auth_subject)`, never a column named after one vendor:
which provider authenticated somebody is an adapter's business (ADR-0004, ADR-0008), and the
pair is what stays unique when there is more than one of them.
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


class Status(StrEnum):
    """Whether this assessor still takes part (ADR-0051).

    `deactivated` is not a deletion and not a lesser identity: the judgments this assessor
    produced stay exactly as they were, because they are facts about what happened. What it
    withdraws is the future — no new work, no way in.
    """

    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class InvalidAssessor(Exception):
    """The assessor breaks an invariant of its aggregate."""


@dataclass
class Assessor:
    """Aggregate root. Identity is `id`; the external credential exists only for humans;
    automated assessors carry their identity in `source_config`."""

    id: UUID
    # The external credential, as `(provider, subject)`. Which provider authenticated
    # somebody is the adapter's business (ADR-0004 for Clerk, ADR-0008 for local), so the
    # pure domain names the shape and not the vendor — and the pair is what stays unique
    # when there is more than one of them.
    auth_provider: str | None = None
    auth_subject: str | None = None
    email: str | None = None
    display_name: str | None = None
    role: Role = Role.EVALUATOR
    expertise: str | None = None
    kind: Kind = Kind.HUMAN
    status: Status = Status.ACTIVE
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
        if not isinstance(self.status, Status):
            try:
                self.status = Status(self.status)
            except ValueError as exc:
                raise InvalidAssessor(f"unknown status: {self.status!r}") from exc
        if self.kind is Kind.HUMAN:
            if not (self.auth_provider or "").strip() or not (self.auth_subject or "").strip():
                raise InvalidAssessor(
                    "a human assessor requires an external credential (auth_provider, auth_subject)"
                )
        else:
            if self.auth_provider is not None or self.auth_subject is not None:
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

    @property
    def is_active(self) -> bool:
        return self.status is Status.ACTIVE

    def deactivate(self) -> None:
        """Withdraw this assessor from the future. Idempotent.

        Nothing is deleted: their evaluations, the assignments they answered and the reports
        naming them are untouched, because they record what happened (ADR-0051, and the same
        argument ADR-0033 makes for content).
        """
        self.status = Status.DEACTIVATED

    def reactivate(self) -> None:
        """They are back. Idempotent, and it restores nothing: nothing was taken away."""
        self.status = Status.ACTIVE

    def set_expertise(self, expertise: str | None) -> bool:
        """Correct the expertise profile. True if anything changed.

        Declared when the invitation was written (ADR-0049), which is the only moment anybody
        knows it — and the only moment it was ever true. People change what they work on, and
        everybody who joined before invitations existed carries nothing at all.

        Blank is the same as absent: an empty box and a box nobody filled say the same thing,
        and storing `""` would make one of them sort and render differently for no reason.
        """
        cleaned = (expertise or "").strip() or None
        if cleaned == self.expertise:
            return False
        self.expertise = cleaned
        return True

    def assign_role(self, role: Role | str) -> None:
        """Change the role. An admin act, never the login flow (ADR-0050)."""
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
