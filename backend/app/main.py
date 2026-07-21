"""FastAPI assembly + DI wiring (outermost layer — ARCHITECTURE.md §1).

Nothing inner imports this module. Routers and policy subscriptions are registered here
as the modules land (blocks 2–4).
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.content_registry.infrastructure.router import router as content_registry_router
from app.platform.db import get_session
from app.platform.security import CurrentAssessor

settings = get_settings()

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
    allow_headers=["Authorization", "Content-Type"],
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


app.include_router(content_registry_router)
