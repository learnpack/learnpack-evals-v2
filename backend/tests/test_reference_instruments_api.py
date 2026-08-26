"""`GET /admin/reference/instruments` — the versions a campaign may pin (ADR-0056).

The human reference instrument's own read surface. It is deliberately NOT under
`/admin/instruments`, which serves the automated evidential argument: two artifacts under a
shared word, and one endpoint returning both would make the console's vocabulary lie.
"""

import pytest
from sqlalchemy import text

from app.platform.db import SessionLocal

SEEDED = "learnpack-pedagogical-2.0.0"
ENDPOINT = "/admin/reference/instruments"


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def reference_version(requires_db):
    """Insert extra `rubric_versions`, with their criteria, and take them away again.

    `cleanup` has no bucket for these — the seeded version is the only one the suite has
    ever needed — so this fixture owns the teardown: criteria first, then the version.
    """
    created: list[str] = []

    def _make(version_id: str, status: str, criteria: int = 2) -> str:
        with SessionLocal() as session:
            session.execute(
                text(
                    """
                    INSERT INTO rubric_versions
                        (id, rubric_id, version, name, status, scope, scale_min, scale_max,
                         response_format)
                    VALUES (:id, 'learnpack-pedagogical', :version, :name, :status,
                            'learnpack course', 1, 5, 'likert')
                    """
                ),
                {
                    "id": version_id,
                    "version": version_id.rsplit("-", 1)[-1],
                    "name": f"Reference {version_id}",
                    "status": status,
                },
            )
            for index in range(criteria):
                session.execute(
                    text(
                        """
                        INSERT INTO criteria
                            (rubric_version_id, criterion_id, ord, dimension, prompt,
                             guidance, anchor_low, anchor_high, qualities, grounded_in,
                             eligible_sources, required_data)
                        VALUES (:v, :c, :ord, 'clarity', 'prompt', 'guidance', 'low', 'high',
                                '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                        """
                    ),
                    {"v": version_id, "c": f"item-{index}", "ord": index},
                )
            session.commit()
        created.append(version_id)
        return version_id

    yield _make

    with SessionLocal() as session:
        for version_id in created:
            session.execute(
                text("DELETE FROM criteria WHERE rubric_version_id = :id"), {"id": version_id}
            )
            session.execute(text("DELETE FROM rubric_versions WHERE id = :id"), {"id": version_id})
        session.commit()


def test_lists_the_seeded_reference_instrument(admin):
    response = admin.get(ENDPOINT)
    assert response.status_code == 200

    row = next(r for r in response.json() if r["rubric_version_id"] == SEEDED)
    assert row["rubric_id"] == "learnpack-pedagogical"
    assert row["name"]
    assert (row["scale_min"], row["scale_max"]) == (1, 5)
    assert row["response_format"] == "likert"
    # The count is what lets somebody tell two versions apart without opening either.
    assert row["criterion_count"] == 12


def test_a_second_published_version_is_offered_alongside_the_first(admin, reference_version):
    """The plural is the point of the endpoint, so it is pinned rather than assumed."""
    second = reference_version("learnpack-pedagogical-test-v98", "published", criteria=3)

    listed = {r["rubric_version_id"]: r for r in admin.get(ENDPOINT).json()}
    assert SEEDED in listed
    assert listed[second]["criterion_count"] == 3


def test_a_draft_version_is_not_offered(admin, reference_version):
    """A campaign cannot open against one, so offering it would offer a failure."""
    draft = reference_version("learnpack-pedagogical-test-v99", "draft")

    assert draft not in {r["rubric_version_id"] for r in admin.get(ENDPOINT).json()}


def test_listing_requires_admin(as_user, cleanup, unique):
    client = as_user(f"user_ada_{unique}", f"ada-{unique}@example.com", "Ada")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    assert client.get(ENDPOINT).status_code == 403
