"""The composition root serves every declared source root (ADR-0035 §1).

The wiring, not the policy: what a locator is made of is pinned in test_local_sources.py.
What matters here is that the bytes are actually reachable at the URL a registered locator
carries — the whole reason the roots are served at all.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import mount_local_sources
from app.modules.evaluand_registry.infrastructure import local_sources


@pytest.fixture
def served(tmp_path, monkeypatch):
    """A `courses/` tree and one declared root, both real, mounted on a fresh app."""
    courses = tmp_path / "courses"
    (courses / "unknown" / "a-course").mkdir(parents=True)
    (courses / "unknown" / "a-course" / "learn.json").write_text('{"slug": "a"}', encoding="utf-8")

    runs = tmp_path / "runs"
    (runs / "batch" / "a-run").mkdir(parents=True)
    (runs / "batch" / "a-run" / "learn.json").write_text('{"slug": "b"}', encoding="utf-8")

    monkeypatch.setattr(local_sources, "COURSES_DIR", courses)
    monkeypatch.setenv("LOCAL_SOURCE_ROOTS", f"runs={runs}")
    get_settings.cache_clear()

    app = FastAPI()
    mount_local_sources(app)
    yield TestClient(app)
    get_settings.cache_clear()


def path_of(url_base: str, *segments: str) -> str:
    """The request path a locator minted from `url_base` resolves to."""
    from urllib.parse import urlsplit

    return "/".join([urlsplit(url_base).path.rstrip("/"), *segments])


def test_a_locator_minted_for_the_builtin_root_resolves(served):
    """Grandfathered: `/packages`, unchanged, because rows written before ADR-0035 point
    there and a registered locator is never rewritten."""
    package = local_sources.package_root(local_sources.builtin_root(), "unknown/a-course")
    locator = package.locator_for("learn.json")

    assert locator.endswith("/packages/unknown/a-course/learn.json")
    assert served.get(path_of(locator)).json() == {"slug": "a"}


def test_a_locator_minted_for_a_declared_root_resolves(served):
    root = local_sources.root_for("runs")
    assert root is not None
    locator = local_sources.package_root(root, "batch/a-run").locator_for("learn.json")

    assert served.get(path_of(locator)).json() == {"slug": "b"}


def test_a_root_whose_directory_is_missing_is_simply_not_served(tmp_path, monkeypatch):
    """A missing root must not stop the app assembling — the guard that keeps a checkout
    without `courses/` booting, now applied to every root."""
    monkeypatch.setattr(local_sources, "COURSES_DIR", tmp_path / "nothing-here")
    monkeypatch.setenv("LOCAL_SOURCE_ROOTS", f"gone={tmp_path / 'gone'}")
    get_settings.cache_clear()

    app = FastAPI()
    mount_local_sources(app)

    assert [route for route in app.routes if getattr(route, "path", None) == "/packages"] == []
    get_settings.cache_clear()
