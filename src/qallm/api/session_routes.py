from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from qallm.session.repo_service import RepoService
from qallm.session.workspace import SessionService

router = APIRouter(prefix="/api/session", tags=["session"])


# ── Request / Response schemas ────────────────────────────────────
class CloneRequest(BaseModel):
    """Request body for cloning a GitHub repository."""

    git_url: str = Field(
        ...,
        description="Public HTTPS GitHub URL to clone.",
        json_schema_extra={"examples": ["https://github.com/owner/repo"]},
    )


class SessionResponse(BaseModel):
    """Returned after a successful upload or clone."""

    session_id: str = Field(..., description="UUID identifying this analysis session.")


class FileListResponse(BaseModel):
    """List of Python files available in the session workspace."""

    session_id: str
    files: list[str] = Field(..., description="Relative paths of extracted .py files.")
    count: int


# ── Endpoints ─────────────────────────────────────────────────────
@router.post(
    "/upload",
    response_model=SessionResponse,
    summary="Upload a ZIP archive",
    response_description="The new session ID",
)
def create_session_from_upload(archive: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a `.zip` file containing Python source code.

    Creates a new session, extracts the archive into an isolated workspace,
    and returns a `session_id` used for all subsequent operations.
    """
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported in this PoC.")

    sid = SessionService.create_session(source_type="upload", github_url=None)
    try:
        SessionService.save_uploaded_zip(sid, archive)
        return {"session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload/extract failed: {e}")


@router.post(
    "/clone",
    response_model=SessionResponse,
    summary="Clone a GitHub repository",
    response_description="The new session ID",
)
def create_session_from_git(req: CloneRequest) -> dict[str, Any]:
    """Clone a public GitHub repository via HTTPS (shallow clone, depth 1).

    Creates a new session, clones the repo into an isolated workspace,
    and returns a `session_id`.
    """
    sid = SessionService.create_session(source_type="github", github_url=req.git_url)
    try:
        RepoService.clone_into_session(sid, req.git_url)
        return {"session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clone failed: {e}")


@router.get(
    "/{session_id}",
    summary="Get session info",
    response_description="Session metadata",
)
def get_session(session_id: str) -> dict[str, Any]:
    """Return session metadata including source type and configuration."""
    info = SessionService.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info


@router.get(
    "/{session_id}/files",
    response_model=FileListResponse,
    summary="List session files",
    response_description="Python files available for analysis",
)
def list_session_files(session_id: str) -> dict[str, Any]:
    """List all Python files extracted or cloned in `workspace_raw`.

    The UI uses this to display checkboxes for file inclusion/exclusion
    before running analysis.
    """
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    files = SessionService.list_workspace_files(session_id)
    return {"session_id": session_id, "files": files, "count": len(files)}
