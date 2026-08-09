"""FastAPI assembly + DI wiring (outermost layer — ARCHITECTURE.md §1).

Nothing inner imports this module. Routers and policy subscriptions are registered here
as the modules land (blocks 2–4).
"""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.content_profiling.infrastructure.policies import (
    register_policies as register_profiling_policies,
)
from app.modules.content_profiling.infrastructure.router import router as content_profiling_router
from app.modules.evaluand_registry.infrastructure.router import (
    evaluand_router as evaluand_admin_router,
)
from app.modules.evaluand_registry.infrastructure.router import router as evaluand_registry_router
from app.modules.evaluation.infrastructure.policies import (
    register_policies as register_evaluation_policies,
)
from app.modules.evaluation.infrastructure.router import router as evaluation_router
from app.modules.evaluation_design.infrastructure.router import router as evaluation_design_router
from app.modules.evaluation_studies.infrastructure.router import (
    instruments_router as studies_matching_router,
)
from app.modules.evaluation_studies.infrastructure.router import router as evaluation_studies_router
from app.modules.golden_dataset.infrastructure.policies import (
    register_policies as register_golden_policies,
)
from app.modules.golden_dataset.infrastructure.router import router as golden_dataset_router
from app.modules.identity.infrastructure.router import admin_router as identity_admin_router
from app.modules.orchestration.infrastructure.policies import register_policies
from app.modules.orchestration.infrastructure.router import (
    admin_router as orchestration_admin_router,
)
from app.modules.orchestration.infrastructure.router import (
    evaluator_router as orchestration_evaluator_router,
)
from app.modules.reporting.infrastructure.router import router as reporting_router
from app.platform.auth_local import DEV_USER_HEADER
from app.platform.db import get_session
from app.platform.dev_router import router as dev_router
from app.platform.events import dispatcher
from app.platform.security import CurrentAssessor

settings = get_settings()

if settings.is_local_auth:
    # Loud on purpose: this process authenticates nobody (ADR-0008). Settings refuses to
    # combine this mode with ENVIRONMENT=production, so this can only be a dev box.
    # ASCII only: a Windows console (cp1252) raises UnicodeEncodeError on anything else,
    # which would turn a warning into a boot failure.
    print(f"WARNING: AUTH_MODE=local - no authentication, identity comes from {DEV_USER_HEADER}")

app = FastAPI(
    title="LearnPack Evals API",
    description="Pedagogical quality evaluation of AI-generated educational content (MVP).",
    version="0.1.0",
)

# Netlify frontend -> Render API. The JWT rides in the Authorization header (ADR-0004).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    # `X-Dev-User` only carries an identity under AUTH_MODE=local; it is inert otherwise, so
    # allowing it unconditionally keeps one CORS config instead of two.
    allow_headers=["Authorization", "Content-Type", DEV_USER_HEADER],
)


@app.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}


class MeResponse(BaseModel):
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None


@app.get("/me", response_model=MeResponse, tags=["identity"])
def me(assessor: CurrentAssessor) -> MeResponse:
    """The current Assessor, created on first login (ADR-0004)."""
    return MeResponse(
        assessor_id=assessor.assessor_id,
        role=assessor.role,
        email=assessor.email,
        display_name=assessor.display_name,
    )


app.include_router(evaluand_registry_router)
app.include_router(evaluand_admin_router)
app.include_router(evaluation_design_router)
app.include_router(evaluation_studies_router)
app.include_router(studies_matching_router)
app.include_router(content_profiling_router)
app.include_router(identity_admin_router)
app.include_router(orchestration_admin_router)
app.include_router(orchestration_evaluator_router)
app.include_router(evaluation_router)
app.include_router(golden_dataset_router)
app.include_router(reporting_router)
app.include_router(dev_router)  # 404s unless AUTH_MODE=local

# The gitignored local courses tree, served over http(s) so locally registered packages get
# fetchable locators (ADR-0027) — that is all it gives them: serving a package's bytes is not
# deploying a course, so a local course declares no consumable URL (ADR-0028). Local-only by
# the ADR-0008 gate; the `is_dir()` check keeps a course-less checkout booting.
COURSES_DIR = Path(__file__).resolve().parents[2] / "courses"
if settings.is_local_auth and COURSES_DIR.is_dir():
    app.mount("/packages", StaticFiles(directory=COURSES_DIR), name="local-packages")

# Policies subscribe here, at wiring time. The MVP's chain (08-code.md §5):
#   EvaluationSubmitted → (orchestration) ContentEvaluationCompleted
#                       → (golden) GoldenReferenceEstablished
# Slice 2 (13-code-qa §5): ContentVersionRegistered → (profiling) profile if accepted;
#   EvaluationCompleted → (evaluation) derive the QualityJudgment + findings.
# Swapping the in-process dispatcher for a real bus later touches only these lines.
register_policies(dispatcher)
register_golden_policies(dispatcher)
register_profiling_policies(dispatcher)
register_evaluation_policies(dispatcher)
