"""Late generator attribution (ADR-0024): a discovery recorded once, never a revision.

The one-way rule is stated twice by design — in the aggregate and in the UPDATE's WHERE —
so it is tested twice: through the use case, and against the repository alone, which is
what would hold if two operators attributed the same content at the same moment.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.modules.evaluand_registry.application.attribute_generator import (
    AttributeGenerator,
    AttributeGeneratorCommand,
)
from app.modules.evaluand_registry.application.errors import ContentNotFound
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnknownGeneratorVersion,
)
from app.modules.evaluand_registry.domain.content import GeneratorAlreadyAttributed
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork

COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


# Two lineages that read as different generators, not as a slip of the same one: since
# ADR-0031 a name one edit from a registered one is refused, and a test that wants two
# examinees has to actually ask for two.
LINEAGE_NAMES = {"a": "attribution-source", "b": "unrelated-toolchain"}


@pytest.fixture
def generator(register_generator_version, unique):
    def _register(suffix: str = "a"):
        return register_generator_version(f"{LINEAGE_NAMES[suffix]}-{unique}")

    return _register


@pytest.fixture
def content(cleanup, unique):
    def _register(generator_version_id=None, suffix: str = "a"):
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            registered = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
            )(
                RegisterContentVersionCommand(
                    package_format="LearnpackV1",
                    external_id=f"attr-course-{suffix}-{unique}",
                    consumable_url=COURSE_URL,
                    generator_version_id=generator_version_id,
                )
            )
        cleanup["contents"].append(registered.id)
        return registered.id

    return _register


def attribute(content_id, generator_version_id, attributed_by=None):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        return AttributeGenerator(
            contents=SqlAlchemyContentRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(
            AttributeGeneratorCommand(
                content_id=content_id,
                generator_version_id=generator_version_id,
                attributed_by=attributed_by or uuid4(),
            )
        )


def row(session, content_id):
    return (
        session.execute(
            text(
                "SELECT generator_version_id, generator_attributed_by, generator_attributed_at "
                "FROM contents WHERE id = :id"
            ),
            {"id": content_id},
        )
        .mappings()
        .one()
    )


def test_attribution_fills_a_declared_unknown(cleanup, unique, session, generator, content):
    generator_id = generator()
    content_id = content()
    who = uuid4()

    attribute(content_id, generator_id, attributed_by=who)

    stored = row(session, content_id)
    assert stored["generator_version_id"] == generator_id
    assert stored["generator_attributed_by"] == who
    assert stored["generator_attributed_at"] is not None  # a discovery is dated

    events = (
        session.execute(
            text("SELECT event_type FROM events WHERE aggregate_id = :id ORDER BY occurred_at"),
            {"id": str(content_id)},
        )
        .scalars()
        .all()
    )
    assert "GeneratorAttributed" in events


def test_a_content_declared_at_registration_carries_no_attribution_provenance(
    session, generator, content
):
    """Null provenance is the mark of a contemporaneous declaration (ADR-0024 §6)."""
    generator_id = generator()
    content_id = content(generator_version_id=generator_id)

    stored = row(session, content_id)
    assert stored["generator_version_id"] == generator_id
    assert stored["generator_attributed_by"] is None
    assert stored["generator_attributed_at"] is None


def test_an_already_attributed_content_is_refused(generator, content):
    """`known → other known` would rewrite what was declared."""
    first, second = generator("a"), generator("b")
    content_id = content(generator_version_id=first)

    with pytest.raises(GeneratorAlreadyAttributed):
        attribute(content_id, second)


def test_attributing_twice_is_refused(generator, content):
    generator_id = generator()
    content_id = content()

    attribute(content_id, generator_id)
    with pytest.raises(GeneratorAlreadyAttributed):
        attribute(content_id, generator_id)


def test_the_database_holds_the_rule_on_its_own(session, generator, content):
    """The repository guard, isolated from the aggregate's: what protects two operators
    attributing the same content at the same moment."""
    generator_id = generator()
    content_id = content()

    with SessionLocal() as first_session:
        repository = SqlAlchemyContentRepository(first_session)
        stored = repository.get_by_id(content_id)
        stored.generator_version_id = generator_id
        stored.generator_attributed_by = uuid4()
        stored.generator_attributed_at = datetime.now(UTC)

        assert repository.attribute_generator(stored) is True
        first_session.commit()
        # The same write again: the row no longer matches `generator_version_id IS NULL`.
        assert repository.attribute_generator(stored) is False


def test_an_unregistered_generator_is_named(content, generator):
    content_id = content()

    with pytest.raises(UnknownGeneratorVersion, match="is not registered"):
        attribute(content_id, uuid4())


def test_attributing_a_missing_content_is_refused(generator):
    with pytest.raises(ContentNotFound):
        attribute(uuid4(), generator())
