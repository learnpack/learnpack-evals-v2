"""SQLAlchemy adapters for Evaluation Design's ports.

Hand-mapped Core statements keep the domain free of SQLAlchemy (ARCHITECTURE.md §1).
`SqlAlchemyRubricRepository` reads the human reference instrument, seeded from
`docs/seed/rubric-v2.json`.
"""

import json

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.evaluation_design.application.dtos import CriterionDTO, RubricSnapshot
from app.modules.evaluation_design.domain.instrument import (
    Claim,
    Criterion,
    InstrumentVersion,
    Sufficiency,
    TaskModelBinding,
)
from app.modules.evaluation_design.domain.reference import DataRequirement


class SqlAlchemyRubricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None:
        version = (
            self._session.execute(
                text(
                    """
                    SELECT id, rubric_id, version, name, status, scope, scale_min, scale_max,
                           response_format
                      FROM rubric_versions
                     WHERE id = :id
                    """
                ),
                {"id": rubric_version_id},
            )
            .mappings()
            .first()
        )
        if version is None:
            return None

        criteria = (
            self._session.execute(
                text(
                    """
                    SELECT criterion_id, ord, dimension, prompt, guidance, anchor_low,
                           anchor_high, qualities, grounded_in, eligible_sources
                      FROM criteria
                     WHERE rubric_version_id = :id
                     ORDER BY ord
                    """
                ),
                {"id": rubric_version_id},
            )
            .mappings()
            .all()
        )

        return RubricSnapshot(
            rubric_version_id=version["id"],
            rubric_id=version["rubric_id"],
            version=version["version"],
            name=version["name"],
            status=version["status"],
            scope=version["scope"],
            scale_min=version["scale_min"],
            scale_max=version["scale_max"],
            response_format=version["response_format"],
            criteria=[
                CriterionDTO(
                    criterion_id=row["criterion_id"],
                    order=row["ord"],
                    dimension=row["dimension"],
                    prompt=row["prompt"],
                    guidance=row["guidance"],
                    anchor_low=row["anchor_low"],
                    anchor_high=row["anchor_high"],
                    qualities=row["qualities"] or [],
                    grounded_in=row["grounded_in"] or [],
                    eligible_sources=row["eligible_sources"] or [],
                )
                for row in criteria
            ],
        )


class SqlAlchemyInstrumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, instrument_version_id: str) -> InstrumentVersion | None:
        head = (
            self._session.execute(
                text(
                    """
                    SELECT id, instrument_id, version, name, purpose, status, published_at,
                           published_by, revision_author, revision_reason, assisted_by,
                           quality_dimensions
                      FROM instrument_versions
                     WHERE id = :id
                    """
                ),
                {"id": instrument_version_id},
            )
            .mappings()
            .first()
        )
        if head is None:
            return None
        return self._assemble(head)

    def list_all(self) -> list[InstrumentVersion]:
        heads = (
            self._session.execute(
                text(
                    """
                    SELECT id, instrument_id, version, name, purpose, status, published_at,
                           published_by, revision_author, revision_reason, assisted_by,
                           quality_dimensions
                      FROM instrument_versions
                     ORDER BY instrument_id, version
                    """
                )
            )
            .mappings()
            .all()
        )
        return [self._assemble(head) for head in heads]

    def _assemble(self, head: RowMapping) -> InstrumentVersion:
        claims = (
            self._session.execute(
                text(
                    """
                    SELECT claim_id, statement, quality_ids, warrants,
                           alternative_explanations, sufficiency
                      FROM instrument_claims
                     WHERE instrument_version_id = :id
                     ORDER BY ord
                    """
                ),
                {"id": head["id"]},
            )
            .mappings()
            .all()
        )
        criteria = (
            self._session.execute(
                text(
                    """
                    SELECT criterion_id, statement, pass_condition, failure_modes, claim_ids,
                           required_data, on_missing_evidence, eligible_sources, condition
                      FROM instrument_criteria
                     WHERE instrument_version_id = :id
                     ORDER BY ord
                    """
                ),
                {"id": head["id"]},
            )
            .mappings()
            .all()
        )
        bindings = (
            self._session.execute(
                text(
                    """
                    SELECT package_format, task_variables
                      FROM instrument_bindings
                     WHERE instrument_version_id = :id
                     ORDER BY package_format
                    """
                ),
                {"id": head["id"]},
            )
            .mappings()
            .all()
        )
        return InstrumentVersion(
            id=head["id"],
            instrument_id=head["instrument_id"],
            version=head["version"],
            name=head["name"],
            purpose=head["purpose"],
            status=head["status"],
            published_at=head["published_at"],
            published_by=head["published_by"],
            revision_author=head["revision_author"],
            revision_reason=head["revision_reason"],
            assisted_by=head["assisted_by"],
            quality_dimensions=dict(head["quality_dimensions"] or {}),
            claims=tuple(
                Claim(
                    claim_id=row["claim_id"],
                    statement=row["statement"],
                    quality_ids=tuple(row["quality_ids"] or []),
                    warrants=tuple(row["warrants"] or []),
                    alternative_explanations=tuple(row["alternative_explanations"] or []),
                    sufficiency=Sufficiency(
                        rule=(row["sufficiency"] or {}).get("rule", "conjunctive")
                    ),
                )
                for row in claims
            ),
            criteria=tuple(
                Criterion(
                    criterion_id=row["criterion_id"],
                    statement=row["statement"],
                    pass_condition=row["pass_condition"],
                    failure_modes=tuple(row["failure_modes"] or []),
                    claim_ids=tuple(row["claim_ids"] or []),
                    required_data=tuple(row["required_data"] or []),
                    on_missing_evidence=row["on_missing_evidence"],
                    eligible_sources=tuple(row["eligible_sources"] or []),
                    condition=row["condition"],
                )
                for row in criteria
            ),
            bindings=tuple(
                TaskModelBinding(
                    package_format=row["package_format"],
                    task_variables=row["task_variables"] or {},
                )
                for row in bindings
            ),
        )

    def save_draft(self, instrument: InstrumentVersion) -> None:
        """Upsert the head and replace the children (draft re-import; CASCADE cleans up)."""
        self._session.execute(
            text(
                """
                INSERT INTO instrument_versions
                    (id, instrument_id, version, name, purpose, status,
                     revision_author, revision_reason, assisted_by)
                VALUES (:id, :iid, :version, :name, :purpose, 'draft',
                        :revision_author, :revision_reason, cast(:assisted_by as jsonb))
                ON CONFLICT (id) DO UPDATE SET
                    name = excluded.name,
                    purpose = excluded.purpose,
                    revision_author = excluded.revision_author,
                    revision_reason = excluded.revision_reason,
                    assisted_by = excluded.assisted_by
                """
            ),
            {
                "id": instrument.id,
                "iid": instrument.instrument_id,
                "version": instrument.version,
                "name": instrument.name,
                "purpose": instrument.purpose,
                "revision_author": instrument.revision_author,
                "revision_reason": instrument.revision_reason,
                "assisted_by": (
                    json.dumps(instrument.assisted_by) if instrument.assisted_by else None
                ),
            },
        )
        for table in ("instrument_claims", "instrument_criteria", "instrument_bindings"):
            self._session.execute(
                text(f"DELETE FROM {table} WHERE instrument_version_id = :id"),  # noqa: S608
                {"id": instrument.id},
            )
        for ord_, claim in enumerate(instrument.claims):
            self._session.execute(
                text(
                    """
                    INSERT INTO instrument_claims
                        (instrument_version_id, claim_id, ord, statement, quality_ids,
                         warrants, alternative_explanations, sufficiency)
                    VALUES (:iv, :cid, :ord, :statement, cast(:qualities as jsonb),
                            cast(:warrants as jsonb), cast(:alternatives as jsonb),
                            cast(:sufficiency as jsonb))
                    """
                ),
                {
                    "iv": instrument.id,
                    "cid": claim.claim_id,
                    "ord": ord_,
                    "statement": claim.statement,
                    "qualities": json.dumps(list(claim.quality_ids)),
                    "warrants": json.dumps(list(claim.warrants)),
                    "alternatives": json.dumps(list(claim.alternative_explanations)),
                    "sufficiency": json.dumps({"rule": claim.sufficiency.rule}),
                },
            )
        for ord_, criterion in enumerate(instrument.criteria):
            self._session.execute(
                text(
                    """
                    INSERT INTO instrument_criteria
                        (instrument_version_id, criterion_id, ord, statement, pass_condition,
                         failure_modes, claim_ids, required_data, on_missing_evidence,
                         eligible_sources, condition)
                    VALUES (:iv, :cid, :ord, :statement, :pass_condition,
                            cast(:failure_modes as jsonb), cast(:claim_ids as jsonb),
                            cast(:required_data as jsonb), :on_missing,
                            cast(:eligible_sources as jsonb), cast(:condition as jsonb))
                    """
                ),
                {
                    "iv": instrument.id,
                    "cid": criterion.criterion_id,
                    "ord": ord_,
                    "statement": criterion.statement,
                    "pass_condition": criterion.pass_condition,
                    "failure_modes": json.dumps(list(criterion.failure_modes)),
                    "claim_ids": json.dumps(list(criterion.claim_ids)),
                    "required_data": json.dumps(list(criterion.required_data)),
                    "on_missing": criterion.on_missing_evidence,
                    "eligible_sources": json.dumps(list(criterion.eligible_sources)),
                    "condition": (json.dumps(criterion.condition) if criterion.condition else None),
                },
            )
        for binding in instrument.bindings:
            self._session.execute(
                text(
                    """
                    INSERT INTO instrument_bindings
                        (instrument_version_id, package_format, task_variables)
                    VALUES (:iv, :package_format, cast(:task_variables as jsonb))
                    """
                ),
                {
                    "iv": instrument.id,
                    "package_format": binding.package_format,
                    "task_variables": json.dumps(binding.task_variables),
                },
            )

    def set_published(self, instrument: InstrumentVersion) -> None:
        self._session.execute(
            text(
                """
                UPDATE instrument_versions
                   SET status = :status, published_at = :published_at,
                       published_by = :published_by,
                       quality_dimensions = cast(:quality_dimensions as jsonb)
                 WHERE id = :id
                """
            ),
            {
                "id": instrument.id,
                "status": instrument.status,
                "published_at": instrument.published_at,
                "published_by": instrument.published_by,
                # Frozen here and nowhere else: publish is the act that pins the vocabulary
                # this version speaks (ADR-0023 §8).
                "quality_dimensions": json.dumps(instrument.quality_dimensions),
            },
        )


class SqlAlchemyDataRequirementRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self) -> dict[str, DataRequirement]:
        rows = (
            self._session.execute(
                text(
                    "SELECT id, definition, aliases, value_domain, grounded_in"
                    " FROM data_requirements"
                )
            )
            .mappings()
            .all()
        )
        return {
            row["id"]: DataRequirement(
                id=row["id"],
                definition=row["definition"],
                aliases=tuple(row["aliases"] or []),
                value_domain=row["value_domain"],
                grounded_in=tuple(row["grounded_in"] or []),
            )
            for row in rows
        }

    def upsert(self, requirement: DataRequirement) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO data_requirements (id, definition, aliases, value_domain, grounded_in)
                VALUES (:id, :definition, cast(:aliases as jsonb),
                        cast(:value_domain as jsonb), cast(:grounded_in as jsonb))
                ON CONFLICT (id) DO UPDATE SET
                    definition = excluded.definition,
                    aliases = excluded.aliases,
                    value_domain = excluded.value_domain,
                    grounded_in = excluded.grounded_in
                """
            ),
            {
                "id": requirement.id,
                "definition": requirement.definition,
                "aliases": json.dumps(list(requirement.aliases)),
                "value_domain": json.dumps(requirement.value_domain),
                "grounded_in": json.dumps(list(requirement.grounded_in)),
            },
        )


class SqlAlchemyReferenceDataRepository:
    """Norm-side ids for publish validation (qualities, frameworks)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def quality_dimensions(self) -> dict[str, str | None]:
        rows = (
            self._session.execute(text("SELECT id, dimension_id FROM qualities")).mappings().all()
        )
        return {row["id"]: row["dimension_id"] for row in rows}

    def framework_ids(self) -> set[str]:
        rows = self._session.execute(text("SELECT id FROM pedagogical_frameworks")).scalars().all()
        return set(rows)
