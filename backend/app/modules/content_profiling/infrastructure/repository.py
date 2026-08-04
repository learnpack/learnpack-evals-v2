"""SQLAlchemy Core repositories for Content Profiling (no declarative models, text() SQL)."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.modules.content_profiling.domain.profile import (
    ContentProfile,
    ProfileEntry,
    ProfileExtra,
)


def _jsonb(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


class SqlAlchemyProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, profile: ContentProfile) -> bool:
        """Idempotent by coordinates: False when (content_id, adapter_version) already
        exists — concurrent policy dispatches must not double-write (ADR-0003)."""
        inserted = self._session.execute(
            text(
                """
                INSERT INTO content_profiles
                    (id, content_id, package_format, adapter_version, status, error,
                     profiled_at)
                VALUES (:id, :content_id, :package_format, :adapter_version, :status,
                        :error, :profiled_at)
                ON CONFLICT (content_id, adapter_version) DO NOTHING
                RETURNING 1
                """
            ),
            {
                "id": profile.id,
                "content_id": profile.content_id,
                "package_format": profile.package_format,
                "adapter_version": profile.adapter_version,
                "status": profile.status,
                "error": profile.error,
                "profiled_at": profile.profiled_at,
            },
        ).scalar()
        if inserted is None:
            return False
        for entry in profile.entries:
            self._session.execute(
                text(
                    """
                    INSERT INTO profile_entries
                        (profile_id, data_requirement_id, value, provenance, quote, locator)
                    VALUES (:profile_id, :requirement_id, cast(:value as jsonb),
                            :provenance, :quote, cast(:locator as jsonb))
                    """
                ),
                {
                    "profile_id": profile.id,
                    "requirement_id": entry.data_requirement_id,
                    "value": _jsonb(entry.value),
                    "provenance": entry.provenance,
                    "quote": entry.quote,
                    "locator": _jsonb(entry.locator),
                },
            )
        for extra in profile.extras:
            self._session.execute(
                text(
                    """
                    INSERT INTO profile_extras (profile_id, name, value, quote, locator)
                    VALUES (:profile_id, :name, cast(:value as jsonb), :quote,
                            cast(:locator as jsonb))
                    """
                ),
                {
                    "profile_id": profile.id,
                    "name": extra.name,
                    "value": _jsonb(extra.value),
                    "quote": extra.quote,
                    "locator": _jsonb(extra.locator),
                },
            )
        return True

    def get_status(self, content_id: UUID, adapter_version: str) -> str | None:
        return self._session.execute(
            text(
                """
                SELECT status FROM content_profiles
                 WHERE content_id = :content_id AND adapter_version = :adapter_version
                """
            ),
            {"content_id": content_id, "adapter_version": adapter_version},
        ).scalar()

    def delete_failed(self, content_id: UUID, adapter_version: str) -> bool:
        """The one exception to immutability: a failed profile is never evidence, and the
        unique coordinates leave no room to keep it next to its retry (13-code §3.4)."""
        deleted = self._session.execute(
            text(
                """
                DELETE FROM content_profiles
                 WHERE content_id = :content_id AND adapter_version = :adapter_version
                   AND status = 'failed'
                RETURNING 1
                """
            ),
            {"content_id": content_id, "adapter_version": adapter_version},
        ).scalar()
        return deleted is not None

    def get(self, content_id: UUID, adapter_version: str | None) -> ContentProfile | None:
        if adapter_version is not None:
            condition, params = (
                "AND adapter_version = :adapter_version",
                {
                    "content_id": content_id,
                    "adapter_version": adapter_version,
                },
            )
        else:
            condition, params = "", {"content_id": content_id}
        head = (
            self._session.execute(
                text(
                    f"""
                    SELECT id, content_id, package_format, adapter_version, status, error,
                           profiled_at
                      FROM content_profiles
                     WHERE content_id = :content_id {condition}
                     ORDER BY (status = 'ok') DESC, profiled_at DESC
                     LIMIT 1
                    """  # noqa: S608 — `condition` is one of two literals above
                ),
                params,
            )
            .mappings()
            .first()
        )
        return self._assemble(head) if head is not None else None

    def list_all(self) -> list[ContentProfile]:
        heads = (
            self._session.execute(
                text(
                    """
                    SELECT id, content_id, package_format, adapter_version, status, error,
                           profiled_at
                      FROM content_profiles
                     ORDER BY profiled_at DESC, id
                    """
                )
            )
            .mappings()
            .all()
        )
        return [self._assemble(head) for head in heads]

    def _assemble(self, head: RowMapping) -> ContentProfile:
        entries = (
            self._session.execute(
                text(
                    """
                    SELECT data_requirement_id, value, provenance, quote, locator
                      FROM profile_entries
                     WHERE profile_id = :id
                     ORDER BY data_requirement_id
                    """
                ),
                {"id": head["id"]},
            )
            .mappings()
            .all()
        )
        extras = (
            self._session.execute(
                text(
                    """
                    SELECT name, value, quote, locator
                      FROM profile_extras
                     WHERE profile_id = :id
                     ORDER BY name
                    """
                ),
                {"id": head["id"]},
            )
            .mappings()
            .all()
        )
        return ContentProfile(
            id=head["id"],
            content_id=head["content_id"],
            package_format=head["package_format"],
            adapter_version=head["adapter_version"],
            status=head["status"],
            error=head["error"],
            profiled_at=head["profiled_at"],
            entries=tuple(
                ProfileEntry(
                    data_requirement_id=entry["data_requirement_id"],
                    provenance=entry["provenance"],
                    value=entry["value"],
                    quote=entry["quote"],
                    locator=entry["locator"],
                )
                for entry in entries
            ),
            extras=tuple(
                ProfileExtra(
                    name=extra["name"],
                    value=extra["value"],
                    quote=extra["quote"],
                    locator=extra["locator"],
                )
                for extra in extras
            ),
        )


class SqlAlchemyAcceptanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def accept(self, package_format: str, adapter_version: str, accepted_by: UUID) -> bool:
        """Idempotent: repeating the act neither rewrites who accepted nor re-emits."""
        inserted = self._session.execute(
            text(
                """
                INSERT INTO extraction_acceptances
                    (package_format, adapter_version, accepted_by)
                VALUES (:package_format, :adapter_version, :accepted_by)
                ON CONFLICT (package_format, adapter_version) DO NOTHING
                RETURNING 1
                """
            ),
            {
                "package_format": package_format,
                "adapter_version": adapter_version,
                "accepted_by": accepted_by,
            },
        ).scalar()
        return inserted is not None

    def is_accepted(self, package_format: str, adapter_version: str) -> bool:
        return (
            self._session.execute(
                text(
                    """
                    SELECT 1 FROM extraction_acceptances
                     WHERE package_format = :package_format
                       AND adapter_version = :adapter_version
                    """
                ),
                {"package_format": package_format, "adapter_version": adapter_version},
            ).scalar()
            is not None
        )
