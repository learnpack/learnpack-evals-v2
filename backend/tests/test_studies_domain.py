"""Study invariants (13-code §10): pin once · dataset fixed at open · publish immutable.

Pure domain — no DB, no fixtures. The report/matching/readiness composition is specified
here too once it lands (also pure, over local DTOs).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.evaluation_studies.domain.model import (
    DatasetEmpty,
    DatasetLocked,
    InstrumentAlreadyPinned,
    InstrumentNotPinned,
    InvalidStudy,
    Study,
    StudyAlreadyOpen,
    StudyAlreadyPublished,
    StudyNotOpen,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def study(**overrides) -> Study:
    defaults = {"id": uuid4(), "purpose": "First LearnpackV1 QA round"}
    return Study(**{**defaults, **overrides})


def composed_study() -> Study:
    s = study()
    s.pin_instrument("learnpack-course-qa-v1")
    s.compose_dataset((uuid4(),), (uuid4(), uuid4()))
    return s


def open_study() -> Study:
    s = composed_study()
    s.open(NOW)
    return s


# ----------------------------------------------------------------------- declaration


def test_a_study_declares_with_a_purpose():
    s = study()
    assert s.status == "declared"
    assert s.instrument_version_id is None


def test_a_blank_purpose_is_invalid():
    with pytest.raises(InvalidStudy):
        study(purpose="   ")


# ----------------------------------------------------------------------- pin once


def test_the_pin_happens_once():
    s = study()
    s.pin_instrument("learnpack-course-qa-v1")

    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("learnpack-course-qa-v2")
    assert s.instrument_version_id == "learnpack-course-qa-v1"


def test_the_pin_is_immutable_after_open():
    s = open_study()
    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("another-version")


# ----------------------------------------------------------------------- prepared is derived


def test_prepared_derives_from_pin_then_compose():
    s = study()
    s.pin_instrument("v1")
    assert s.status == "declared"
    s.compose_dataset((), (uuid4(),))
    assert s.status == "prepared"


def test_prepared_derives_from_compose_then_pin():
    s = study()
    s.compose_dataset((uuid4(),), (uuid4(),))
    assert s.status == "declared"
    s.pin_instrument("v1")
    assert s.status == "prepared"


def test_the_recipe_evolves_freely_before_open():
    s = composed_study()
    replacement = (uuid4(),)
    s.compose_dataset((), replacement)
    assert s.content_ids == replacement
    assert s.brief_ids == ()


# ----------------------------------------------------------------------- dataset fixed at open


def test_open_fixes_the_dataset():
    s = open_study()
    with pytest.raises(DatasetLocked):
        s.compose_dataset((), (uuid4(),))


def test_open_requires_the_pin():
    s = study()
    s.compose_dataset((), (uuid4(),))
    with pytest.raises(InstrumentNotPinned):
        s.open(NOW)


def test_open_requires_a_dataset():
    s = study()
    s.pin_instrument("v1")
    with pytest.raises(DatasetEmpty):
        s.open(NOW)


def test_open_happens_once():
    s = open_study()
    with pytest.raises(StudyAlreadyOpen):
        s.open(NOW)


def test_open_records_when():
    s = composed_study()
    s.open(NOW)
    assert s.status == "open"
    assert s.opened_at == NOW


# ----------------------------------------------------------------------- publish immutable


def test_publish_requires_an_open_round():
    s = composed_study()
    with pytest.raises(StudyNotOpen):
        s.publish(uuid4(), NOW)


def test_publish_records_the_human_act():
    s = open_study()
    who = uuid4()
    s.publish(who, NOW)
    assert s.status == "published"
    assert s.published_by == who
    assert s.published_at == NOW


def test_published_is_immutable():
    s = open_study()
    s.publish(uuid4(), NOW)

    with pytest.raises(StudyAlreadyPublished):
        s.publish(uuid4(), NOW)
    with pytest.raises(StudyAlreadyPublished):
        s.open(NOW)
    with pytest.raises(StudyAlreadyPublished):
        s.compose_dataset((), (uuid4(),))
    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("another")
