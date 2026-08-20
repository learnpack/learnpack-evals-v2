"""The wrapper `ProfileContent` puts around a fetcher for the length of one extraction.

Why it exists rather than a rule the adapters follow: an adapter's entry builders are
deliberately independent — each reads and cites its own artifact without asking what another
read — so the same file is legitimately asked for more than once. The repetition is stopped
where it costs nothing to stop it. No DB, no network.
"""

from app.modules.content_profiling.application.profile_content import _ReadOnce


class CountingFetcher:
    def __init__(self) -> None:
        self.singles: list[str] = []
        self.waves: list[list[str]] = []

    def fetch(self, locator: str) -> bytes:
        self.singles.append(locator)
        return locator.encode()

    def fetch_all(self, locators):
        self.waves.append(list(locators))
        return {locator: locator.encode() for locator in locators}


def test_the_second_read_of_an_artifact_never_reaches_the_fetcher():
    inner = CountingFetcher()
    reader = _ReadOnce(inner)

    assert reader.fetch("plan.json") == b"plan.json"
    assert reader.fetch("plan.json") == b"plan.json"

    assert inner.singles == ["plan.json"]


def test_a_wave_asks_only_for_what_is_missing_and_asks_for_it_together():
    """The half-remembered case is the one worth pinning: a wave that dropped to one read at
    a time whenever a single file was already in hand would lose exactly what the wave is
    for."""
    inner = CountingFetcher()
    reader = _ReadOnce(inner)
    reader.fetch("a.md")

    answered = reader.fetch_all(["a.md", "b.md", "c.md"])

    assert answered == {"a.md": b"a.md", "b.md": b"b.md", "c.md": b"c.md"}
    assert inner.waves == [["b.md", "c.md"]]  # one group, and not the one already read
    assert inner.singles == ["a.md"]


def test_a_wave_of_things_already_read_asks_for_nothing():
    inner = CountingFetcher()
    reader = _ReadOnce(inner)
    reader.fetch_all(["a.md", "b.md"])

    assert reader.fetch_all(["b.md", "a.md"]) == {"a.md": b"a.md", "b.md": b"b.md"}
    assert inner.waves == [["a.md", "b.md"]]
