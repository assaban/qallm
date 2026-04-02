from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from qallm.analysis.containers import build_analyzer_registry, build_normalizer_registry
from qallm.analysis.pipeline import AnalysisService
from qallm.analysis.selection_service import SelectionService
from qallm.session.workspace import SessionService

router = APIRouter(prefix="/api", tags=["analysis"])

# Build once at module level
_analysis_service = AnalysisService(
    build_analyzer_registry(),
    build_normalizer_registry(),
)


# ── Request / Response schemas ────────────────────────────────────
class AnalyseRequest(BaseModel):
    """Request body for running static analysis."""

    session_id: str = Field(..., description="UUID of the session to analyse.")
    selected_files: list[str] | None = Field(
        None,
        description="Files to include. If omitted, all files are analysed.",
    )
    analyzers: list[str] | None = Field(
        None,
        description="Tool names to run (e.g. `['bandit', 'ruff']`). If omitted, all four tools run.",
        json_schema_extra={"examples": [["bandit", "ruff", "radon", "trufflehog"]]},
    )


class FindingSummary(BaseModel):
    """Aggregate counts by severity and type."""

    total: int
    by_severity: dict[str, int]
    by_type: dict[str, int]


class AnalyseResponse(BaseModel):
    """Result of a full analysis run."""

    session_id: str
    summary: FindingSummary
    findings: list[dict[str, Any]] = Field(..., description="Unified findings from all tools.")


class ReportResponse(BaseModel):
    """Persisted findings report for a session."""

    session_id: str
    count: int
    findings: list[dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────
@router.get(
    "/analyzers",
    summary="List available tools",
    response_description="Names of registered static analysis tools",
)
def list_analyzers() -> list[str]:
    """Return the names of all static analysis tools currently available.

    Tools: **Bandit** (security), **Ruff** (code smells), **Radon**
    (cyclomatic complexity), **TruffleHog** (secrets detection).
    """
    return _analysis_service.analyzers.list()


@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    summary="Run static analysis",
    response_description="Unified findings report with summary counts",
)
def analyse(req: AnalyseRequest) -> dict[str, Any]:
    """Run selected static analysis tools on session files and return a
    unified findings report.

    **Steps performed:**
    1. Apply file selection (`workspace_raw` → `workspace`)
    2. Execute each analyzer (Bandit, Ruff, Radon, TruffleHog)
    3. Normalize raw tool output into unified `Finding` objects
    4. Persist `findings_unified.json` for later retrieval
    5. Return summary counts + full findings list
    """
    sid = req.session_id

    if not SessionService.session_exists(sid):
        raise HTTPException(status_code=404, detail="Session not found")

    # Auto-select: if selected_files provided, apply selection first;
    # otherwise copy ALL files from raw → active workspace
    if req.selected_files is not None:
        SelectionService.apply_selection(sid, req.selected_files)
    else:
        raw = SessionService.workspace_raw_dir(sid)
        if raw.exists():
            all_files = SessionService.list_workspace_files(sid)
            SelectionService.apply_selection(sid, all_files)

    try:
        findings = _analysis_service.run(sid, selected_tools=req.analyzers)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    summary = AnalysisService.summarize(findings)
    return {
        "session_id": sid,
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
    }


@router.get(
    "/session/{session_id}/report",
    response_model=ReportResponse,
    summary="Get persisted report",
    response_description="Previously computed findings",
)
def get_report(session_id: str) -> dict[str, Any]:
    """Retrieve the persisted unified findings report for a session.

    The report is written during `POST /api/analyse` and can be
    retrieved later without re-running the tools.
    """
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    p = SessionService.reports_dir(session_id) / "findings_unified.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="No analysis run yet")

    findings = json.loads(p.read_text(encoding="utf-8"))
    return {
        "session_id": session_id,
        "count": len(findings),
        "findings": findings,
    }
