"""Identity's Published Language.

`AssessorDTO` is the only thing other modules ever see — they never import
`identity.domain` (ARCHITECTURE.md §3).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AutomatedIdentity:
    """What identifies an automated assessor: `(name, version)` is the artifact
    (ADR-0016 clause 2), and the lineage it owes itself to completes it (ADR-0019 §1).

    The rest of `source_config` — the coverage — is not published here: it is the
    assessor-package registry's to state, and it says the same thing for every version
    of the artifact whether or not a row exists.
    """

    name: str
    version: str
    instrument_id: str


@dataclass(frozen=True)
class AssessorDTO:
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None
    # The Source axis (GLOSSARY): `human` or `automated`. Two kinds with a real structural
    # difference (ADR-0016), which a consumer listing them has to be able to tell apart.
    kind: str = "human"
    # Present exactly when `kind == "automated"`.
    automated: AutomatedIdentity | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
