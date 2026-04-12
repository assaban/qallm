"""API routes for RL-guided test generation (T-022).

Provides HTTP endpoints for running verification on existing sessions.
The Jupyter trigger (T-023) and web UI (T-024) will call these endpoints.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from qallm.repair.containers import build_llm_registry
from qallm.session.workspace import SessionService
from qallm.verification.extractor import extract_functions_from_source
from qallm.verification.loop import TestGenerationLoop, save_session
from qallm.verification.models import OracleType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verification", tags=["verification"])

_llm_registry = build_llm_registry()


class VerifyRequest(BaseModel):
    """Request body for running RL-guided test generation."""

    session_id: str = Field(..., description="UUID of the session to verify.")
    model: str | None = Field(None, description="LLM model name. If omitted, uses default.")
    rounds: int = Field(5, ge=1, le=20, description="Number of RL feedback rounds.")
    oracle: OracleType = Field("crash", description="Oracle type for test generation.")
    timeout: int = Field(60, ge=5, le=300, description="Execution timeout per round in seconds.")


class VerifyFunctionRequest(BaseModel):
    """Request body for verifying a single function by name."""

    session_id: str
    function_name: str
    model: str | None = None
    rounds: int = Field(5, ge=1, le=20)
    oracle: OracleType = "crash"
    timeout: int = Field(60, ge=5, le=300)


@router.get("/models", summary="List available LLM models for verification")
def list_models() -> dict[str, Any]:
    """Return the list of available and configured LLM models."""
    return {
        "available": _llm_registry.list(),
        "configured": _llm_registry.list_configured(),
    }


@router.get("/functions/{session_id}", summary="List extractable functions in a session")
def list_functions(session_id: str) -> dict[str, Any]:
    """Extract and list all public functions from the session's workspace."""
    if not SessionService.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    workspace = SessionService.workspace_active_dir(session_id)
    if not workspace.exists():
        workspace = SessionService.workspace_raw_dir(session_id)

    functions = []
    for py_file in workspace.rglob("*.py"):
        source_code = py_file.read_text(encoding="utf-8")
        funcs = extract_functions_from_source(source_code, filepath=str(py_file))
        for func in funcs:
            functions.append(
                {
                    "name": func.name,
                    "file": py_file.name,
                    "lineno": func.lineno,
                    "args": [{"name": a, "type": t} for a, t in func.args],
                    "docstring": func.docstring,
                }
            )

    return {"session_id": session_id, "functions": functions}


@router.post("/run", summary="Run RL-guided test generation on a session")
def run_verification(req: VerifyRequest) -> dict[str, Any]:
    """Run RL-guided test generation on all extractable functions in a session.

    Extracts functions from the session's workspace files, runs the
    TestGenerationLoop on each function, and returns aggregated results.
    """
    if not SessionService.session_exists(req.session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Read source files from workspace
    workspace = SessionService.workspace_active_dir(req.session_id)
    if not workspace.exists():
        workspace = SessionService.workspace_raw_dir(req.session_id)

    py_files = list(workspace.rglob("*.py"))
    if not py_files:
        raise HTTPException(status_code=400, detail="No Python files found in session workspace")

    # Pick LLM model
    model_name = req.model or "gpt-4o-mini"
    try:
        llm = _llm_registry.pick(model_name)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' not found. Available: {_llm_registry.list()}",
        )

    if not llm.is_configured():
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_name}' is not configured. Set the required API key.",
        )

    # Extract functions and run verification
    all_sessions = []
    total_functions = 0
    total_bugs = 0

    for py_file in py_files:
        source_code = py_file.read_text(encoding="utf-8")
        module_name = py_file.stem
        functions = extract_functions_from_source(source_code, filepath=str(py_file))

        if not functions:
            continue

        total_functions += len(functions)

        for func in functions:
            loop = TestGenerationLoop(
                llm=llm,
                rounds=req.rounds,
                oracle=req.oracle,
                timeout=req.timeout,
            )
            tests_dir = SessionService.generated_tests_dir(req.session_id)
            session = loop.run(func, source_code, module_name=module_name, persist_dir=tests_dir)
            all_sessions.append(asdict(session))
            total_bugs += session.final_bugs

            # Persist individual session
            reports_dir = SessionService.reports_dir(req.session_id)
            session_file = reports_dir / f"verification_{func.name}.json"
            save_session(session, session_file)

    # Persist aggregate report
    aggregate = {
        "session_id": req.session_id,
        "model": model_name,
        "oracle": req.oracle,
        "rounds_per_function": req.rounds,
        "total_functions": total_functions,
        "total_bugs": total_bugs,
        "functions": all_sessions,
    }

    reports_dir = SessionService.reports_dir(req.session_id)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "verification_aggregate.json").write_text(
        json.dumps(aggregate, indent=2, default=str),
        encoding="utf-8",
    )

    return aggregate
