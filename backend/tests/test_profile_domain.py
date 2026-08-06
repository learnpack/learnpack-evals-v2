"""ContentProfile domain invariants (design 12 §Content Profiling; ADR-0009). No DB."""

import pytest

from app.modules.content_profiling.domain import events
from app.modules.content_profiling.domain.profile import (
    ContentProfile,
    InvalidProfile,
    ProfileEntry,
    ProfileExtra,
)
from app.shared.domain.ids import new_id

# The namespace IS the declared shapes since ADR-0020: every canonical id carries one.
VALUE_DOMAINS: dict[str, dict] = {
    "learning_objectives": {"type": "string_list"},
    "target_audience": {"type": "string"},
    "prerequisites": {"type": "string_list"},
}
CAPABILITIES = frozenset({"learning_objectives", "target_audience"})


def entry(requirement_id: str = "learning_objectives", **overrides) -> ProfileEntry:
    fields = {
        "data_requirement_id": requirement_id,
        "provenance": "declared_structured",
        "value": ["Explain X"],
        "quote": '["Explain X"]',
        "locator": {"source": "metadata", "key": "learningObjectives"},
    }
    fields.update(overrides)
    return ProfileEntry(**fields)


def absent(requirement_id: str) -> ProfileEntry:
    return ProfileEntry(data_requirement_id=requirement_id, provenance="absent")


def ok_profile(**overrides) -> ContentProfile:
    fields = {
        "id": new_id(),
        "content_id": new_id(),
        "package_format": "LearnpackV1",
        "adapter_version": "learnpack-v1-adapter/1",
        "capabilities": CAPABILITIES,
        "value_domains": VALUE_DOMAINS,
        "entries": (entry(), absent("target_audience")),
    }
    fields.update(overrides)
    return ContentProfile.ok(**fields)


# --- entry invariants (ADR-0009) -------------------------------------------------------


def test_declared_entry_without_quote_is_not_evidence():
    with pytest.raises(InvalidProfile, match="quote"):
        entry(quote=None)
    with pytest.raises(InvalidProfile, match="quote"):
        entry(quote="   ")


def test_declared_entry_requires_locator_and_value():
    with pytest.raises(InvalidProfile, match="locator"):
        entry(locator=None)
    with pytest.raises(InvalidProfile, match="value"):
        entry(value=None)


def test_absent_entry_carries_no_value_and_no_quote():
    assert absent("learning_objectives").value is None
    with pytest.raises(InvalidProfile, match="absent"):
        entry(provenance="absent")


def test_inferred_provenance_does_not_exist():
    with pytest.raises(InvalidProfile, match="inferred"):
        entry(provenance="inferred")


# --- aggregate invariants (design 12) --------------------------------------------------


def test_ok_profile_holds_exactly_one_entry_per_capability():
    profile = ok_profile()
    assert profile.status == "ok"
    assert {e.data_requirement_id for e in profile.entries} == set(CAPABILITIES)


def test_capability_without_entry_is_rejected_absence_must_be_explicit():
    with pytest.raises(InvalidProfile, match="absent"):
        ok_profile(entries=(entry(),))  # target_audience capability, no entry


def test_entry_beyond_declared_capabilities_is_rejected():
    with pytest.raises(InvalidProfile, match="beyond"):
        ok_profile(entries=(entry(), absent("target_audience"), absent("prerequisites")))


def test_capabilities_outside_canonical_namespace_are_rejected():
    with pytest.raises(InvalidProfile, match="namespace"):
        ok_profile(
            capabilities=frozenset({*CAPABILITIES, "made_up_datum"}),
            entries=(entry(), absent("target_audience"), absent("made_up_datum")),
        )


# --- invariant 5: the declared shape (ADR-0020) ----------------------------------------


def test_a_value_that_does_not_match_its_declared_domain_is_rejected():
    """The defence against a second adapter covering an id with a different shape."""
    with pytest.raises(InvalidProfile, match="value domain"):
        ok_profile(entries=(entry(value=[{"objective": "Explain X"}]), absent("target_audience")))


def test_the_violation_names_the_requirement_and_what_it_expected():
    with pytest.raises(InvalidProfile) as raised:
        ok_profile(entries=(entry(value="Explain X"), absent("target_audience")))
    message = str(raised.value)
    assert "learning_objectives" in message
    assert "expected string_list" in message


def test_an_absent_entry_is_not_shape_checked():
    """Absence is the finding, not a shape — and it carries no value to check."""
    profile = ok_profile(entries=(absent("learning_objectives"), absent("target_audience")))
    assert profile.status == "ok"


def test_duplicate_entries_are_rejected():
    with pytest.raises(InvalidProfile, match="duplicate"):
        ok_profile(entries=(entry(), entry(), absent("target_audience")))


def test_extras_never_use_canonical_ids():
    with pytest.raises(InvalidProfile, match="canonical"):
        ok_profile(extras=(ProfileExtra(name="prerequisites", value=["x"]),))
    profile = ok_profile(extras=(ProfileExtra(name="estimated_duration", value="4h"),))
    assert profile.extras[0].name == "estimated_duration"


def test_failed_profile_requires_error_and_has_no_entries():
    profile = ContentProfile.failed(
        id=new_id(),
        content_id=new_id(),
        package_format="LearnpackV1",
        adapter_version="learnpack-v1-adapter/1",
        error="manifest is not valid JSON",
    )
    assert profile.status == "failed"
    assert profile.entries == ()
    with pytest.raises(InvalidProfile, match="error"):
        ContentProfile.failed(
            id=new_id(),
            content_id=new_id(),
            package_format="LearnpackV1",
            adapter_version="learnpack-v1-adapter/1",
            error="  ",
        )


# --- event payloads (camelCase, no entries) --------------------------------------------


def test_content_profiled_payload_carries_coordinates_only():
    profile = ok_profile()
    event = events.content_profiled(profile)
    assert event.event_type == "ContentProfiled"
    assert event.aggregate_id == str(profile.id)
    assert event.payload == {
        "profileId": str(profile.id),
        "contentId": str(profile.content_id),
        "packageFormat": "LearnpackV1",
        "adapterVersion": "learnpack-v1-adapter/1",
    }


def test_content_profiling_failed_payload_carries_the_error():
    profile = ContentProfile.failed(
        id=new_id(),
        content_id=new_id(),
        package_format="LearnpackV1",
        adapter_version="learnpack-v1-adapter/1",
        error="boom",
    )
    event = events.content_profiling_failed(profile)
    assert event.event_type == "ContentProfilingFailed"
    assert event.payload["error"] == "boom"


def test_extraction_accepted_is_keyed_by_format_and_version():
    admin_id = new_id()
    event = events.extraction_accepted("LearnpackV1", "learnpack-v1-adapter/1", admin_id)
    assert event.aggregate_id == "LearnpackV1:learnpack-v1-adapter/1"
    assert event.payload == {
        "packageFormat": "LearnpackV1",
        "adapterVersion": "learnpack-v1-adapter/1",
        "acceptedBy": str(admin_id),
    }
