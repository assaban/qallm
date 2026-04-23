from __future__ import annotations

import json
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


@router.get("/list", summary="List all existing sessions")
def list_all_sessions() -> dict[str, Any]:
    return {"sessions": SessionService.list_all_sessions()}


@router.get("/{session_id}/analysis-history", summary="List analysis rounds with findings counts")
def get_analysis_history(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    return {
        "session_id": session_id,
        "rounds": SessionService.list_analysis_rounds(session_id),
    }


@router.get("/{session_id}/diff/{filepath:path}", summary="Get diff between original and active code")
def get_file_diff(session_id: str, filepath: str) -> dict[str, Any]:
    _require_session(session_id)
    import difflib

    raw_dir = SessionService.workspace_raw_dir(session_id)
    active_dir = SessionService.workspace_active_dir(session_id)

    raw_file = raw_dir / filepath
    active_file = active_dir / filepath

    original = raw_file.read_text(encoding="utf-8") if raw_file.exists() else ""
    current = active_file.read_text(encoding="utf-8") if active_file.exists() else ""

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=f"original/{filepath}",
            tofile=f"repaired/{filepath}",
        )
    )

    return {
        "filepath": filepath,
        "original": original,
        "current": current,
        "diff": "".join(diff_lines),
        "changed": original != current,
    }


@router.get("/{session_id}/download/tests", summary="Download generated tests as JSON")
def download_tests(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    tests_dir = SessionService.generated_tests_dir(session_id)
    test_files = {}
    if tests_dir.exists():
        for f in sorted(tests_dir.rglob("*.py")):
            test_files[f.name] = f.read_text(encoding="utf-8")
    return {"session_id": session_id, "tests": test_files, "count": len(test_files)}


@router.get("/{session_id}/dashboard", summary="Session dashboard summary")
def get_dashboard(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    import os

    reports_dir = SessionService.reports_dir(session_id)
    tests_dir = SessionService.generated_tests_dir(session_id)

    # Analysis
    analysis_rounds = SessionService.list_analysis_rounds(session_id)
    latest_findings = 0
    if analysis_rounds:
        latest_findings = analysis_rounds[-1]["total"]

    # Repair
    history_dir = SessionService.repair_history_dir(session_id)
    repair_rounds = len(list(history_dir.iterdir())) if history_dir.exists() else 0

    # Tests
    total_coverage = 0
    total_bugs = 0
    func_count = 0
    if reports_dir.exists():
        for vf in reports_dir.glob("verification_*.json"):
            if vf.name == "verification_report.json" or vf.name == "verification_aggregate.json":
                continue
            try:
                data = json.loads(vf.read_text(encoding="utf-8"))
                func_count += 1
                rounds = data.get("rounds", [])
                if rounds:
                    last = rounds[-1]
                    cov = last.get("cumulative_coverage", 0) or 0
                    bugs = last.get("cumulative_bugs", 0) or 0
                    total_coverage += cov
                    total_bugs += bugs
            except Exception:
                pass

    avg_coverage = round(total_coverage / func_count, 1) if func_count else 0
    test_file_count = sum(1 for _ in tests_dir.rglob("*.py")) if tests_dir.exists() else 0

    created = os.path.getmtime(SessionService.session_json_path(session_id))

    return {
        "session_id": session_id,
        "created_at": created,
        "analysis_rounds": len(analysis_rounds),
        "latest_findings": latest_findings,
        "repair_rounds": repair_rounds,
        "functions_tested": func_count,
        "avg_coverage": avg_coverage,
        "total_bugs": total_bugs,
        "test_files": test_file_count,
    }


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


@router.get(
    "/{session_id}/versions",
    summary="List available code versions (original + repair rounds)",
)
def list_versions(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    rounds = SessionService.list_repair_rounds(session_id)
    return {"session_id": session_id, "versions": rounds}


@router.post(
    "/{session_id}/restore/{round_num}",
    summary="Restore a repair history snapshot to the active workspace",
)
def restore_version(session_id: str, round_num: int) -> dict[str, Any]:
    _require_session(session_id)
    success = SessionService.restore_repair_round(session_id, round_num)
    if not success:
        raise HTTPException(status_code=404, detail=f"Round {round_num} not found")
    return {"session_id": session_id, "restored_round": round_num, "status": "ok"}


@router.get(
    "/{session_id}/analysis-history",
    summary="List analysis rounds with finding counts",
)
@router.get(
    "/{session_id}/diff/{filepath:path}",
    summary="Get unified diff between original and active code",
)
@router.get(
    "/{session_id}/download/tests",
    summary="Download generated test files",
)
@router.get(
    "/{session_id}/paper-metrics",
    summary="Compute paper quality metrics (CS, MI, CoDu, CoDe, LoC, CC)",
)
def get_paper_metrics(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    from qallm.analysis.paper_metrics import compute_paper_metrics

    return compute_paper_metrics(session_id)


@router.get(
    "/{session_id}/paper-metrics-history",
    summary="Paper metrics across rounds (for Table 5/6 generation)",
)
def get_paper_metrics_history_endpoint(session_id: str) -> dict[str, Any]:
    _require_session(session_id)
    from qallm.analysis.paper_metrics import get_paper_metrics_history

    return {"session_id": session_id, "rounds": get_paper_metrics_history(session_id)}
