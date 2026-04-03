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

analysis_service = AnalysisService(
    build_analyzer_registry(),
    build_normalizer_registry(),
)


class AnalyseRequest(BaseModel):
    """Request body for running static analysis."""

    session_id: str = Field(..., description="UUID of the session to analyse.")
    selected_files: list[str] | None = Field(
        default=None,
        description="Files to include. If omitted, all analyzable files are selected.",
    )
    analyzers: list[str] | None = Field(
        default=None,
        description="Tool names to run. If omitted, all registered tools run.",
        json_schema_extra={"examples": [["bandit", "ruff", "radon", "trufflehog"]]},
    )


class FindingSummary(BaseModel):
    total: int
    by_severity: dict[str, int]
    by_type: dict[str, int]


class AnalyseResponse(BaseModel):
    session_id: str
    summary: FindingSummary
    findings: list[dict[str, Any]] = Field(
        ...,
        description="Unified findings from all selected tools.",
    )


class ReportResponse(BaseModel):
    session_id: str
    count: int
    findings: list[dict[str, Any]]


@router.get(
    "/analyzers",
    summary="List available static analysis tools",
    response_description="Names of registered analyzers",
)
def list_analyzers() -> list[str]:
    return analysis_service.analyzers.list()


@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    summary="Run static analysis",
    response_description="Unified findings report with summary counts",
)
def analyse(req: AnalyseRequest) -> dict[str, Any]:
    session_id = req.session_id

    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    selected_files = req.selected_files
    if selected_files is None:
        selected_files = SessionService.list_workspace_files(session_id)

    if not selected_files:
        raise HTTPException(
            status_code=400,
            detail="No analyzable files found in the session.",
        )

    try:
        SelectionService.apply_selection(session_id, selected_files)
        findings = analysis_service.run(session_id, selected_tools=req.analyzers)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = AnalysisService.summarize(findings)
    return {
        "session_id": session_id,
        "summary": summary,
        "findings": [finding.to_dict() for finding in findings],
    }


@router.get(
    "/session/{session_id}/report",
    response_model=ReportResponse,
    summary="Get persisted analysis report",
    response_description="Previously computed unified findings",
)
def get_report(session_id: str) -> dict[str, Any]:
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    report_path = SessionService.reports_dir(session_id) / "findings_unified.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No analysis run yet")

    findings = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "session_id": session_id,
        "count": len(findings),
        "findings": findings,
    }
