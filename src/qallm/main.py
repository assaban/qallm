"""QALLM — Quality Assessment of AI-Generated Code.

Single FastAPI application consolidating analysis, repair, and verification.
Serves the web frontend and exposes API routes for CLI/Jupyter integration.
"""

import logging
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from qallm.api.analysis_routes import router as analysis_router
from qallm.api.repair_routes import router as repair_router
from qallm.api.session_routes import router as session_router

# Future: from qallm.api.verification_routes import router as verification_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
_logger = logging.getLogger(__name__)
_BOOT_TIME = time.monotonic()

app = FastAPI(
    title="QALLM — Quality Assessment Tool",
    description=(
        "Static analysis, LLM-based repair, and RL-guided test generation "
        "for Python code and Jupyter notebooks."
    ),
    version="0.3.0",
    openapi_tags=[
        {"name": "health", "description": "Service liveness checks."},
        {"name": "session", "description": "Workspace management — upload files, clone repositories, parse notebooks."},
        {"name": "analysis", "description": "Run static analysis tools (Bandit, Radon, Ruff, TruffleHog)."},
        {"name": "repair", "description": "LLM-based code repair for flagged issues."},
        {"name": "verification", "description": "RL-guided test generation and execution (coming soon)."},
    ],
)


# ── Health ────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    import shutil

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
        "uptime_seconds": round(time.monotonic() - _BOOT_TIME, 1),
    }


# ── API routers ───────────────────────────────────────────────────
app.include_router(session_router)
app.include_router(analysis_router)
app.include_router(repair_router)
# Future: app.include_router(verification_router)


# ── Static frontend ───────────────────────────────────────────────
# Serve web UI at root (must be last so API routes take priority)
try:
    from pathlib import Path

    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception:
    _logger.warning("Web frontend static files not found — running API-only mode")
