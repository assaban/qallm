from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from qallm.api.analysis_routes import router as analysis_router
from qallm.api.health_routes import router as health_router
from qallm.api.repair_routes import router as repair_router
from qallm.api.session_routes import router as session_router
from qallm.api.web_routes import router as web_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web" / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="QALLM: Quality Assessment Tool",
        description=(
            "Static analysis, LLM-based repair, and RL-guided test generation for Python code and Jupyter notebooks."
        ),
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "health", "description": "Service liveness checks."},
            {
                "name": "session",
                "description": "Workspace management — upload files, clone repositories, parse notebooks.",
            },
            {
                "name": "analysis",
                "description": "Run static analysis tools (Bandit, Radon, Ruff, TruffleHog).",
            },
            {
                "name": "repair",
                "description": "LLM-based code repair for flagged issues.",
            },
            {
                "name": "verification",
                "description": "RL-guided test generation and execution (coming soon).",
            },
            {"name": "web", "description": "Browser frontend."},
        ],
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(health_router)
    app.include_router(web_router)
    app.include_router(session_router)
    app.include_router(analysis_router)
    app.include_router(repair_router)

    return app


app = create_app()
