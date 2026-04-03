from __future__ import annotations

import shutil
import time

from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])

BOOT_TIME = time.monotonic()


@router.get("")
@router.get("/")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "qallm",
        "version": "0.3.0",
        "tools": {
            "bandit": shutil.which("bandit") is not None,
            "ruff": shutil.which("ruff") is not None,
            "radon": shutil.which("radon") is not None,
            "trufflehog": shutil.which("trufflehog") is not None,
        },
        "uptime_seconds": round(time.monotonic() - BOOT_TIME, 1),
    }


@router.get("/ready")
def ready() -> dict:
    return {"status": "ready"}


@router.get("/llm")
def llm_health() -> dict:
    return {"status": "healthy", "service": "llm"}


@router.get("/agent")
def agent_health() -> dict:
    return {"status": "healthy", "service": "agent"}
