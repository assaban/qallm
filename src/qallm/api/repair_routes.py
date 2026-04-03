from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from qallm.analysis.containers import build_analyzer_registry, build_normalizer_registry
from qallm.analysis.pipeline import AnalysisService
from qallm.repair.repair_service import list_providers, run_repair
from qallm.session.workspace import SessionService

router = APIRouter(prefix="/api", tags=["repair"])

analysis_service = AnalysisService(
    build_analyzer_registry(),
    build_normalizer_registry(),
)


class RepairRequest(BaseModel):
    """Request body for LLM repair."""

    finding_ids: list[str] | None = Field(
        default=None,
        description=(
            "Specific finding IDs to repair. If omitted, the repair service "
            "selects the top findings by severity."
        ),
    )
    max_issues: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of findings to repair.",
    )
    provider: str | None = Field(
        default=None,
        description=(
            "LLM provider/model to use. If omitted, the system auto-routes "
            "based on severity and configuration."
        ),
    )


def _require_session(session_id: str) -> None:
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


def _require_report(session_id: str, filename: str, detail: str) -> None:
    report_path = SessionService.reports_dir(session_id) / filename
    if not report_path.exists():
        raise HTTPException(status_code=400, detail=detail)


@router.get(
    "/llm/providers",
    summary="List LLM providers",
    response_description="Available, configured, and default LLM providers",
)
def get_providers() -> dict[str, Any]:
    return list_providers()


@router.get(
    "/llm/rates",
    summary="Get LLM pricing rates",
    response_description="Per-token pricing in USD for known models",
)
def get_rates() -> dict[str, Any]:
    from qallm.llm.base import MODEL_RATES

    return {
        "unit": "USD per 1,000,000 tokens",
        "rates": {
            model: {
                "input_per_1m_usd": rates["input"],
                "output_per_1m_usd": rates["output"],
            }
            for model, rates in MODEL_RATES.items()
        },
        "note": "Local Ollama models do not incur API cost.",
    }


@router.post(
    "/repair/{session_id}",
    summary="Repair findings via LLM",
    response_description="Generated patches with token usage and provider metadata",
)
def repair(
    session_id: str,
    req: RepairRequest = Body(default_factory=RepairRequest),
) -> dict[str, Any]:
    _require_session(session_id)
    _require_report(
        session_id,
        "findings_unified.json",
        "No analysis run yet. Run POST /api/analyse first.",
    )

    try:
        result = run_repair(
            session_id=session_id,
            finding_ids=req.finding_ids,
            max_issues=req.max_issues,
            provider=req.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"session_id": session_id, **result}


@router.get(
    "/repair/{session_id}/report",
    summary="Get repair report",
    response_description="Persisted repair patches and token usage",
)
def get_repair_report(session_id: str) -> dict[str, Any]:
    _require_session(session_id)

    report_path = SessionService.reports_dir(session_id) / "repair_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No repair run yet")

    return json.loads(report_path.read_text(encoding="utf-8"))


@router.post(
    "/verify/{session_id}",
    summary="Re-run static analysis to verify repairs",
    response_description="Before/after comparison including resolved, remaining, and new findings",
)
def verify(
    session_id: str,
    analyzers: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    _require_session(session_id)
    _require_report(
        session_id,
        "findings_unified.json",
        "No analysis report found. Run POST /api/analyse first.",
    )
    _require_report(
        session_id,
        "repair_report.json",
        "No repair report found. Run POST /api/repair/{session_id} first.",
    )

    try:
        report = analysis_service.verify(
            session_id=session_id,
            selected_tools=analyzers,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"session_id": session_id, **asdict(report)}


@router.get(
    "/verify/{session_id}/report",
    summary="Get persisted verification report",
    response_description="Previously computed verification results",
)
def get_verification_report(session_id: str) -> dict[str, Any]:
    _require_session(session_id)

    report_path = SessionService.reports_dir(session_id) / "verification_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No verification run yet")

    return json.loads(report_path.read_text(encoding="utf-8"))
