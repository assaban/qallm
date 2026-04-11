from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from qallm.session.config import settings
from qallm.session.schemas import SessionConfig


class SessionService:
    """Owns session directory layout and persistence."""

    ANALYZABLE_SUFFIXES = {".py", ".ipynb"}

    @staticmethod
    def _base_dir() -> Path:
        return Path(settings.DATA_DIR)

    @staticmethod
    def session_dir(session_id: str) -> Path:
        return SessionService._base_dir() / session_id

    @staticmethod
    def workspace_raw_dir(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "workspace_raw"

    @staticmethod
    def workspace_active_dir(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "workspace"

    @staticmethod
    def reports_dir(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "reports"

    @staticmethod
    def generated_tests_dir(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "generated_tests"

    @staticmethod
    def session_json_path(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "session.json"

    @staticmethod
    def session_exists(session_id: str) -> bool:
        return SessionService.session_json_path(session_id).exists()

    @staticmethod
    def create_session(source_type: str, github_url: str | None) -> str:
        session_id = str(uuid.uuid4())
        session_dir = SessionService.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        SessionService.workspace_raw_dir(session_id).mkdir(parents=True, exist_ok=True)
        SessionService.workspace_active_dir(session_id).mkdir(parents=True, exist_ok=True)
        SessionService.reports_dir(session_id).mkdir(parents=True, exist_ok=True)

        cfg = SessionConfig(source_type=source_type, github_url=github_url)
        payload = {
            "session_id": session_id,
            "config": cfg.model_dump(),
        }

        SessionService.session_json_path(session_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return session_id

    @staticmethod
    def get_session_info(session_id: str) -> dict[str, Any] | None:
        session_path = SessionService.session_json_path(session_id)
        if not session_path.exists():
            return None
        return json.loads(session_path.read_text(encoding="utf-8"))

    @staticmethod
    def list_workspace_files(session_id: str) -> list[str]:
        raw_dir = SessionService.workspace_raw_dir(session_id)
        if not raw_dir.exists():
            return []

        files: list[str] = []
        for path in raw_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in SessionService.ANALYZABLE_SUFFIXES:
                files.append(path.relative_to(raw_dir).as_posix())

        files.sort()
        return files
