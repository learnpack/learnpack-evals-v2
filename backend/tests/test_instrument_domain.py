"""Publish invariants and lifecycle of the Instrument aggregate (design 12) — no DB."""

import pytest

from app.modules.evaluation_design.domain.instrument import (
    Claim,
    Criterion,
    InstrumentImmutable,
    InstrumentVersion,
    InvalidInstrument,
    Sufficiency,
    TaskModelBinding,
)
from app.modules.evaluation_design.domain.reference import DataRequirement, InvalidDataRequirement
from app.shared.domain.ids import new_id

QUALITIES = {"objectives-observable", "instruction-application"}
FRAMEWORKS = {"Biggs", "Merrill"}
NAMESPACE = {"learning_objectives", "practice_exercises"}


def claim(**overrides):
    base = {
        "claim_id": "cl-objectives",
        "statement": "The course declares observable learning objectives.",
        "quality_ids": ("objectives-observable",),
        "warrants": ("Biggs",),
        "alternative_explanations": ("objectives live in the body but not in the manifest",),
    }
    return Claim(**(base | overrides))


def criterion(**overrides):
    base = {
        "criterion_id": "cr-min-objectives",
        "pass_condition": "At least 2 learning objectives are declared.",
        "failure_modes": ("fewer than 2 objectives declared",),
        "claim_ids": ("cl-objectives",),
        "required_data": ("learning_objectives",),
    }
    return Criterion(**(base | overrides))


def instrument(**overrides):
    base = {
        "id": "demo-qa-v1",
        "instrument_id": "demo-qa",
        "version": "v1",
        "name": "Demo QA",
        "purpose": "internal QA of generated courses",
        "claims": (claim(),),
        "criteria": (criterion(),),
        "bindings": (TaskModelBinding(package_format="LearnpackV1"),),
    }
    return InstrumentVersion(**(base | overrides))


def publish(inst, **overrides):
    kwargs = {
        "published_by": new_id(),
        "known_data_requirements": NAMESPACE,
        "known_qualities": QUALITIES,
        "known_frameworks": FRAMEWORKS,
    } | overrides
    inst.publish(**kwargs)
    return inst


# ------------------------------------------------------------------ value objects


def test_sufficiency_v0_is_conjunctive_only():
    assert Sufficiency().rule == "conjunctive"
    with pytest.raises(InvalidInstrument, match="not implemented"):
        Sufficiency(rule="weighted_average")  # compensatory: forbidden (ADR-0011)


def test_claim_statement_must_be_one_sentence():
    with pytest.raises(InvalidInstrument, match="one sentence"):
        claim(statement="Line one.\nLine two.")
    with pytest.raises(InvalidInstrument, match="one sentence"):
        claim(statement="x" * 301)


@pytest.mark.parametrize(
    "overrides",
    [
        {"quality_ids": ()},
        {"warrants": ()},
        {"alternative_explanations": ("   ",)},
        {"statement": "  "},
    ],
)
def test_incomplete_claims_are_rejected(overrides):
    with pytest.raises(InvalidInstrument):
        claim(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"pass_condition": " "},
        {"failure_modes": ()},
        {"claim_ids": ()},
        {"required_data": ()},
        {"on_missing_evidence": "invent_a_score"},
        {"eligible_sources": ()},
        {"eligible_sources": ("llm",)},  # old taxonomy died with ADR-0016
    ],
)
def test_incomplete_criteria_are_rejected(overrides):
    with pytest.raises(InvalidInstrument):
        criterion(**overrides)


def test_data_requirement_definition_is_mandatory():
    with pytest.raises(InvalidDataRequirement, match="definition"):
        DataRequirement(
            id="learning_objectives", definition="  ", value_domain={"type": "string_list"}
        )


def test_data_requirement_value_domain_is_mandatory():
    """ADR-0020: the shape is declared where the id is minted, or nothing can check it."""
    with pytest.raises(InvalidDataRequirement, match="value_domain"):
        DataRequirement(
            id="learning_objectives", definition="The declared objectives.", value_domain={}
        )


@pytest.mark.parametrize(
    "domain",
    [
        {"type": "list_of_strings"},  # not a type this vocabulary knows
        {"type": "record"},  # a record without fields declares nothing
        {"type": "record_list", "feilds": {"slug": {"type": "string"}}},  # typo
        {"type": "string", "fields": {"slug": {"type": "string"}}},  # fields do not apply
        {"type": "record_list", "fields": {"slug": {"type": "strng"}}},  # bad nested type
    ],
)
def test_a_malformed_value_domain_is_rejected_at_minting(domain):
    with pytest.raises(InvalidDataRequirement):
        DataRequirement(
            id="lesson_inventory", definition="The declared lesson index.", value_domain=domain
        )


# ------------------------------------------------------------------ publish invariants


def test_a_complete_draft_publishes():
    inst = publish(instrument())
    assert inst.is_published
    assert inst.published_at is not None


def test_publish_requires_a_binding():
    with pytest.raises(InvalidInstrument, match="binding"):
        publish(instrument(bindings=()))


def test_publish_requires_every_claim_to_be_evidenced():
    lonely = claim(claim_id="cl-lonely", statement="Nobody evidences this claim.")
    with pytest.raises(InvalidInstrument, match="cl-lonely has no evidencing criterion"):
        publish(instrument(claims=(claim(), lonely)))


def test_publish_rejects_criteria_pointing_to_unknown_claims():
    stray = criterion(criterion_id="cr-stray", claim_ids=("cl-ghost",))
    with pytest.raises(InvalidInstrument, match="unknown claim cl-ghost"):
        publish(instrument(criteria=(criterion(), stray)))


def test_publish_rejects_data_outside_the_namespace():
    needy = criterion(required_data=("unminted_datum",))
    with pytest.raises(InvalidInstrument, match="outside the\\s+namespace: unminted_datum"):
        publish(instrument(criteria=(needy,)))


def test_publish_rejects_unknown_qualities_and_frameworks():
    with pytest.raises(InvalidInstrument, match="unknown qualities"):
        publish(instrument(claims=(claim(quality_ids=("ghost-quality",)),)))
    with pytest.raises(InvalidInstrument, match="unknown frameworks"):
        publish(instrument(claims=(claim(warrants=("Ghostism",)),)))


def test_publish_reports_every_problem_at_once():
    """Atomic act: the author sees the full list, not one error per attempt."""
    broken = instrument(
        claims=(claim(), claim(claim_id="cl-lonely", statement="Lonely.")),
        criteria=(criterion(required_data=("unminted_datum",)),),
        bindings=(),
    )
    with pytest.raises(InvalidInstrument) as excinfo:
        publish(broken)
    message = str(excinfo.value)
    assert "unminted_datum" in message
    assert "cl-lonely" in message
    assert "binding" in message


# ------------------------------------------------------------------ lifecycle


def test_published_versions_are_immutable():
    inst = publish(instrument())
    with pytest.raises(InstrumentImmutable, match="bump the version"):
        inst.require_editable()
    with pytest.raises(InstrumentImmutable):
        publish(inst)  # double publish


def test_id_convention_is_enforced():
    with pytest.raises(InvalidInstrument, match="instrument_id"):
        instrument(id="otherid-v1")


def test_duplicate_child_ids_are_rejected():
    with pytest.raises(InvalidInstrument, match="duplicate claim ids"):
        instrument(claims=(claim(), claim()))
    with pytest.raises(InvalidInstrument, match="duplicate criterion ids"):
        instrument(criteria=(criterion(), criterion()))
