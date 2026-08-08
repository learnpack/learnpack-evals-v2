"""The empirical thresholds, pinned against the whole frozen corpus.

The quantitative criteria carry numbers that were chosen by measuring five real packages,
not by taste (`docs/MEASUREMENT.md`). A threshold like that drifts silently: someone
adjusts a regex in the measure, every value moves a little, and the criterion keeps
returning verdicts that no longer mean what the document says they mean. This is the net
under that — it asserts the verdict each package produces, so a change that moves one has
to move this file too, and say why.

If you are here because this test failed: do not retune the number to make it pass. Read
`docs/MEASUREMENT.md` first, and redo the comparison it records.

No DB and no network: extraction plus the measure, exactly as an evaluation runs them.
"""

import statistics

import pytest

from app.modules.content_profiling.infrastructure.adapters.learnpack_v1 import LearnpackV1Adapter
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.evaluation.infrastructure.assessors.structural import measures
from app.modules.evaluation.infrastructure.assessors.structural.executors import (
    LEXICAL_LOAD_SPIKE,
)
from tests.test_learnpack_adapter import FIXTURES, fixture_package

REAL_PACKAGES = (
    "ai-concepts-an-exploration-inside-ai",
    "html-fundamentals",
    "introduction-to-generative-ai",
    "object-representation-in-python",
    "orchestrating-a-multi-agent-system-in-langgraph",
)

# course -> (median lexical load, how far the worst lesson sits above it, that lesson).
# Rounded to 3 decimals: the fourth is below anything the threshold can act on.
LEXICAL_LOAD = {
    "ai-concepts-an-exploration-inside-ai": (1.716, 0.318, "05.1-hallucinations-in-ai"),
    "html-fundamentals": (1.575, 0.095, "02.2-build-a-navigation-menu"),
    "introduction-to-generative-ai": (1.788, 0.137, "04.2-advantages-and-tradeoffs"),
    "object-representation-in-python": (1.656, 0.243, "02.1-dot-notation"),
    "orchestrating-a-multi-agent-system-in-langgraph": (
        1.725,
        0.221,
        "00.0-welcome-to-multi-agent-systems",
    ),
}


@pytest.fixture
def entries():
    adapter, fetcher = LearnpackV1Adapter(), FilesystemPackageFetcher(FIXTURES)

    def _entries(course: str):
        extracted, _ = adapter.extract(fixture_package(course), fetcher)
        return {entry.data_requirement_id: entry for entry in extracted}

    return _entries


@pytest.mark.parametrize("course", REAL_PACKAGES)
def test_lexical_load_of_each_package_is_what_the_threshold_was_set_against(course, entries):
    expected_median, expected_spike, expected_worst = LEXICAL_LOAD[course]
    bodies = entries(course)["lesson_bodies"].value

    by_slug = measures.lexical_load_by_lesson(list(bodies))
    # Every lesson in every real package is long enough to carry a stable mean, so the
    # short-lesson guard never silently shrinks the population these numbers came from.
    assert len(by_slug) == len(bodies)

    median = statistics.median(by_slug.values())
    worst = max(by_slug, key=lambda slug: by_slug[slug])
    assert round(median, 3) == expected_median
    assert round(by_slug[worst] - median, 3) == expected_spike
    assert worst == expected_worst


def test_the_threshold_separates_the_corpus_rather_than_passing_or_failing_all_of_it():
    """A threshold that everything clears, or that nothing does, measures nothing. This is
    the property that made 0.20 the choice and not a rounder number."""
    spikes = {course: spike for course, (_, spike, _) in LEXICAL_LOAD.items()}
    over = {course for course, spike in spikes.items() if spike > LEXICAL_LOAD_SPIKE}
    assert over == {
        "ai-concepts-an-exploration-inside-ai",
        "object-representation-in-python",
        "orchestrating-a-multi-agent-system-in-langgraph",
    }
    # The closest package sits 0.02 above the line: near enough that a careless change to
    # the measure would flip it, which is exactly why this file exists.
    margins = [
        spike - LEXICAL_LOAD_SPIKE for spike in spikes.values() if spike > LEXICAL_LOAD_SPIKE
    ]
    assert min(margins) < 0.03


# course -> (lessons declared CODE that ship nothing, lessons shipping an exercise
# without being declared CODE). Both directions are real defects and both were found in
# the corpus, in different packages.
TYPE_DELIVERY_MISMATCHES = {
    "ai-concepts-an-exploration-inside-ai": ([], []),
    "html-fundamentals": ([], ["01.2", "02.2", "03.2", "04.1", "04.2", "05.1", "06.1"]),
    "introduction-to-generative-ai": ([], []),
    "object-representation-in-python": (["01.3", "02.3"], ["01.0", "01.2", "02.1"]),
    "orchestrating-a-multi-agent-system-in-langgraph": ([], []),
}


@pytest.mark.parametrize("course", REAL_PACKAGES)
def test_declared_lesson_type_against_delivered_exercises(course, entries):
    expected_missing, expected_undeclared = TYPE_DELIVERY_MISMATCHES[course]
    extracted = entries(course)
    exercises = {
        record["lessonSlug"]: record["codeExercises"]
        for record in extracted["lesson_activities"].value
    }

    missing, undeclared = [], []
    for lesson in extracted["lesson_inventory"].value:
        declares_code = str(lesson.get("type") or "").upper() == "CODE"
        delivers = bool(exercises.get(lesson["slug"]))
        if declares_code and not delivers:
            missing.append(str(lesson["lessonId"]))
        elif delivers and not declares_code:
            undeclared.append(str(lesson["lessonId"]))

    assert missing == expected_missing
    assert undeclared == expected_undeclared


def test_a_course_declaring_no_code_practice_passes_on_a_fact_not_on_an_empty_set():
    """Three of the five packages declare no CODE lesson AND ship no exercise. They pass
    because the correspondence holds, not because there was nothing to check — the reason
    the criterion is stated in both directions."""
    silent = [
        course
        for course, (missing, undeclared) in TYPE_DELIVERY_MISMATCHES.items()
        if not missing and not undeclared
    ]
    assert len(silent) == 3
