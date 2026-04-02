from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from qallm.session.config import settings
from qallm.session.schemas import SessionConfig


class SessionService:
    """
    Owns session directory layout and persistence.
    """

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
    def session_json_path(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "session.json"

    @staticmethod
    def session_exists(session_id: str) -> bool:
        return SessionService.session_dir(session_id).exists()

    @staticmethod
    def create_session(source_type: str, github_url: str | None) -> str:
        sid = str(uuid.uuid4())
        sdir = SessionService.session_dir(sid)
        sdir.mkdir(parents=True, exist_ok=True)

        # Create standard dirs
        SessionService.workspace_raw_dir(sid).mkdir(parents=True, exist_ok=True)
        SessionService.workspace_active_dir(sid).mkdir(parents=True, exist_ok=True)
        SessionService.reports_dir(sid).mkdir(parents=True, exist_ok=True)

        # Default config (later updated via UI selection)
        cfg = SessionConfig(source_type=source_type, github_url=github_url)

        payload = {
            "session_id": sid,
            "config": cfg.model_dump(),
        }
        SessionService.session_json_path(sid).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return sid

    @staticmethod
    def get_session_info(session_id: str) -> dict[str, Any] | None:
        p = SessionService.session_json_path(session_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def save_uploaded_zip(session_id: str, archive: UploadFile) -> None:
        """
        Extract uploaded zip to workspace_raw.
        """
        raw_dir = SessionService.workspace_raw_dir(session_id)
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Save upload to disk first (safer than streaming into zipfile)
        zip_path = SessionService.session_dir(session_id) / "upload.zip"
        with zip_path.open("wb") as f:
            shutil.copyfileobj(archive.file, f)

        # Extract
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(raw_dir)

        # Clean common macOS junk
        SessionService._clean_workspace(raw_dir)

    @staticmethod
    def _clean_workspace(raw_dir: Path) -> None:
        """
        Remove noise that breaks tools (e.g., __MACOSX, .DS_Store).
        """
        junk_names = {"__MACOSX", ".DS_Store"}
        for p in list(raw_dir.rglob("*")):
            if p.name in junk_names:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        p.unlink()
                    except Exception:
                        pass

        # remove AppleDouble files: "._*"
        for p in list(raw_dir.rglob("._*")):
            try:
                p.unlink()
            except Exception:
                pass

    @staticmethod
    def list_workspace_files(session_id: str) -> list[str]:
        """
        List files under workspace_raw as relative, unix-style paths.
        """
        raw_dir = SessionService.workspace_raw_dir(session_id)
        if not raw_dir.exists():
            return []

        files: list[str] = []
        for p in raw_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(raw_dir).as_posix()
                files.append(rel)

        files.sort()
        return files
