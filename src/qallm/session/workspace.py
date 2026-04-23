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
    def repair_history_dir(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "repair_history"

    @staticmethod
    def snapshot_workspace(session_id: str) -> int:
        """Copy the current active workspace into repair_history/round_NN.

        Returns the round number of the snapshot.
        """
        import shutil

        history_dir = SessionService.repair_history_dir(session_id)
        history_dir.mkdir(parents=True, exist_ok=True)

        # Determine next round number
        existing = sorted(history_dir.iterdir()) if history_dir.exists() else []
        round_num = len(existing) + 1
        round_dir = history_dir / f"round_{round_num:02d}"

        # Copy active workspace to snapshot
        workspace = SessionService.workspace_active_dir(session_id)
        if workspace.exists():
            shutil.copytree(workspace, round_dir)
        else:
            round_dir.mkdir(parents=True)

        return round_num

    @staticmethod
    def list_repair_rounds(session_id: str) -> list[dict[str, Any]]:
        """List all available repair history snapshots.

        Returns a list of dicts with round number, path, and file count.
        Always includes round 0 (original/workspace_raw).
        """
        raw_dir = SessionService.workspace_raw_dir(session_id)
        raw_count = sum(1 for f in raw_dir.rglob("*.py")) if raw_dir.exists() else 0

        rounds = [{"round": 0, "label": "Original (workspace_raw)", "files": raw_count}]

        history_dir = SessionService.repair_history_dir(session_id)
        if history_dir.exists():
            for round_dir in sorted(history_dir.iterdir()):
                if round_dir.is_dir() and round_dir.name.startswith("round_"):
                    num = int(round_dir.name.split("_")[1])
                    file_count = sum(1 for f in round_dir.rglob("*.py"))
                    rounds.append(
                        {
                            "round": num,
                            "label": f"Before repair round {num}",
                            "files": file_count,
                        }
                    )

        # Current workspace (latest version)
        active = SessionService.workspace_active_dir(session_id)
        active_count = sum(1 for f in active.rglob("*.py")) if active.exists() else 0
        last_round = rounds[-1]["round"] if rounds else 0
        rounds.append(
            {
                "round": last_round + 1,
                "label": "Current (active workspace)",
                "files": active_count,
            }
        )

        return rounds

    @staticmethod
    def restore_repair_round(session_id: str, round_num: int) -> bool:
        """Restore a repair history snapshot to the active workspace.

        Round 0 restores from workspace_raw. Other rounds restore from
        repair_history/round_NN.

        Returns True on success, False if round not found.
        """
        import shutil

        if round_num == 0:
            source = SessionService.workspace_raw_dir(session_id)
        else:
            source = SessionService.repair_history_dir(session_id) / f"round_{round_num:02d}"

        if not source.exists():
            return False

        workspace = SessionService.workspace_active_dir(session_id)
        # Clear active workspace and copy from source
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(source, workspace)
        return True

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

    @staticmethod
    def list_all_sessions() -> list[dict[str, Any]]:
        """List all sessions with summary info."""
        import os

        base = SessionService._base_dir()
        if not base.exists():
            return []

        sessions = []
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            session_json = entry / "session.json"
            if not session_json.exists():
                continue

            info = json.loads(session_json.read_text(encoding="utf-8"))
            session_id = info.get("session_id", entry.name)
            config = info.get("config", {})

            reports_dir = entry / "reports"
            has_analysis = (reports_dir / "findings_unified.json").exists()
            has_repair = (reports_dir / "repair_report.json").exists()
            has_tests = (entry / "generated_tests").exists() and any((entry / "generated_tests").iterdir())

            history_dir = entry / "repair_history"
            repair_rounds = len(list(history_dir.iterdir())) if history_dir.exists() else 0

            created = os.path.getmtime(session_json)

            sessions.append(
                {
                    "session_id": session_id,
                    "source_type": config.get("source_type", "unknown"),
                    "created_at": created,
                    "has_analysis": has_analysis,
                    "has_repair": has_repair,
                    "has_tests": has_tests,
                    "repair_rounds": repair_rounds,
                }
            )

        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions

    @staticmethod
    def list_analysis_rounds(session_id: str) -> list[dict[str, Any]]:
        """List all versioned analysis rounds."""
        reports = SessionService.reports_dir(session_id)
        rounds = []
        for path in sorted(reports.glob("findings_round_*.json")):
            num = int(path.stem.split("_")[-1])
            findings = json.loads(path.read_text(encoding="utf-8"))
            by_sev = {}
            for f in findings:
                sev = f.get("severity", "LOW")
                by_sev[sev] = by_sev.get(sev, 0) + 1
            rounds.append(
                {
                    "round": num,
                    "total": len(findings),
                    "by_severity": by_sev,
                }
            )
        return rounds
