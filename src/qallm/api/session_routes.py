from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from qallm.services.ingest_service import IngestService
from qallm.session.workspace import SessionService

router = APIRouter(prefix="/api/session", tags=["session"])


class CloneRequest(BaseModel):
    """Request body for cloning a Git repository."""

    git_url: str = Field(
        ...,
        description="Public HTTPS GitHub URL to clone.",
        json_schema_extra={"examples": ["https://github.com/owner/repo"]},
    )


class SessionResponse(BaseModel):
    session_id: str = Field(..., description="UUID identifying this analysis session.")


class FileListResponse(BaseModel):
    session_id: str
    files: list[str] = Field(
        ...,
        description="Relative paths of analyzable files (.py, .ipynb).",
    )
    count: int


def _require_session(session_id: str) -> None:
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


@router.post(
    "/upload",
    response_model=SessionResponse,
    summary="Upload a ZIP archive",
    response_description="The new session ID",
)
def create_session_from_upload(archive: UploadFile = File(...)) -> dict[str, Any]:
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip uploads are supported in this proof of concept.",
        )

    try:
        session_id = IngestService.create_session_from_upload(archive)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload/extract failed: {exc}") from exc

    return {"session_id": session_id}


@router.post(
    "/clone",
    response_model=SessionResponse,
    summary="Clone a GitHub repository",
    response_description="The new session ID",
)
def create_session_from_git(req: CloneRequest) -> dict[str, Any]:
    try:
        session_id = IngestService.create_session_from_git(req.git_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clone failed: {exc}") from exc

    return {"session_id": session_id}


@router.get(
    "/{session_id}",
    summary="Get session info",
    response_description="Session metadata",
)
def get_session(session_id: str) -> dict[str, Any]:
    info = SessionService.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info


@router.get(
    "/{session_id}/files",
    response_model=FileListResponse,
    summary="List session files",
    response_description="Analyzable files available for analysis",
)
def list_session_files(session_id: str) -> dict[str, Any]:
    _require_session(session_id)

    files = SessionService.list_workspace_files(session_id)
    return {
        "session_id": session_id,
        "files": files,
        "count": len(files),
    }
