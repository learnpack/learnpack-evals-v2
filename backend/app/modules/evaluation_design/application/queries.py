"""Read-only query port of Rubric Authoring — `getRubric(version)` (05-connect.md).

Evaluation stores only the `rubricVersion` and reads the rubric through here; it never
touches `rubric_versions` / `criteria` itself.
"""

from app.modules.evaluation_design.application.dtos import RubricSnapshot
from app.modules.evaluation_design.application.ports import RubricRepositoryPort


def get_rubric(rubrics: RubricRepositoryPort, rubric_version_id: str) -> RubricSnapshot | None:
    return rubrics.get_snapshot(rubric_version_id)
