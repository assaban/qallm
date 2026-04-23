"""Session workspace management with round-based layout.

Layout:
    data/<session-id>/
    ├── original/                 # uploaded code, never modified
    ├── baseline_tests/           # tests on original code
    │   ├── generated_tests/
    │   └── reports/
    ├── round_01/
    │   ├── repaired_code/
    │   ├── generated_tests/
    │   └── reports/
    ├── round_02/ ...
    └── session.json
"""

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

    # ── Base paths ────────────────────────────────────────

    @staticmethod
    def _base_dir() -> Path:
        return Path(settings.DATA_DIR)

    @staticmethod
    def session_dir(session_id: str) -> Path:
        return SessionService._base_dir() / session_id

    @staticmethod
    def session_json_path(session_id: str) -> Path:
        return SessionService.session_dir(session_id) / "session.json"

    @staticmethod
    def session_exists(session_id: str) -> bool:
        return SessionService.session_json_path(session_id).exists()

    # ── Directory helpers ─────────────────────────────────

    @staticmethod
    def original_dir(session_id: str) -> Path:
        """Uploaded/cloned code. Never modified after ingest."""
        return SessionService.session_dir(session_id) / "original"

    @staticmethod
    def baseline_tests_dir(session_id: str) -> Path:
        """Tests generated on original (unrepaired) code."""
        return SessionService.session_dir(session_id) / "baseline_tests"

    @staticmethod
    def baseline_reports_dir(session_id: str) -> Path:
        d = SessionService.baseline_tests_dir(session_id) / "reports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def baseline_generated_tests_dir(session_id: str) -> Path:
        d = SessionService.baseline_tests_dir(session_id) / "generated_tests"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def round_dir(session_id: str, round_num: int) -> Path:
        return SessionService.session_dir(session_id) / f"round_{round_num:02d}"

    @staticmethod
    def round_repaired_code_dir(session_id: str, round_num: int) -> Path:
        d = SessionService.round_dir(session_id, round_num) / "repaired_code"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def round_generated_tests_dir(session_id: str, round_num: int) -> Path:
        d = SessionService.round_dir(session_id, round_num) / "generated_tests"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def round_reports_dir(session_id: str, round_num: int) -> Path:
        d = SessionService.round_dir(session_id, round_num) / "reports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Backward compatibility aliases ────────────────────
    # These map old names to new layout so callers don't break
    # during the transition. Remove after full migration.

    @staticmethod
    def workspace_raw_dir(session_id: str) -> Path:
        """Alias for original_dir (backward compat)."""
        return SessionService.original_dir(session_id)

    @staticmethod
    def workspace_active_dir(session_id: str) -> Path:
        """Returns the latest round's repaired_code dir,
        or original/ if no rounds exist yet."""
        current = SessionService.current_round(session_id)
        if current == 0:
            return SessionService.original_dir(session_id)
        return SessionService.round_repaired_code_dir(session_id, current)

    @staticmethod
    def reports_dir(session_id: str) -> Path:
        """Returns the latest round's reports dir,
        or baseline reports if no rounds exist."""
        current = SessionService.current_round(session_id)
        if current == 0:
            return SessionService.baseline_reports_dir(session_id)
        return SessionService.round_reports_dir(session_id, current)

    @staticmethod
    def generated_tests_dir(session_id: str) -> Path:
        """Returns latest round's generated_tests dir."""
        current = SessionService.current_round(session_id)
        if current == 0:
            return SessionService.baseline_generated_tests_dir(session_id)
        return SessionService.round_generated_tests_dir(session_id, current)

    @staticmethod
    def repair_history_dir(session_id: str) -> Path:
        """Backward compat: return session dir (rounds are the history now)."""
        return SessionService.session_dir(session_id)

    # ── Round management ──────────────────────────────────

    @staticmethod
    def current_round(session_id: str) -> int:
        """Return the latest round number, or 0 if no rounds exist."""
        base = SessionService.session_dir(session_id)
        if not base.exists():
            return 0
        rounds = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith("round_"))
        if not rounds:
            return 0
        return int(rounds[-1].name.split("_")[1])

    @staticmethod
    def next_round(session_id: str) -> int:
        """Create the next round directory and return its number."""
        num = SessionService.current_round(session_id) + 1
        rd = SessionService.round_dir(session_id, num)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "repaired_code").mkdir(exist_ok=True)
        (rd / "generated_tests").mkdir(exist_ok=True)
        (rd / "reports").mkdir(exist_ok=True)
        return num

    @staticmethod
    def code_dir_for_round(session_id: str, round_num: int) -> Path:
        """Return the code directory to read for a given round.

        Round 0 = original/, Round N = round_N/repaired_code/.
        """
        if round_num <= 0:
            return SessionService.original_dir(session_id)
        return SessionService.round_repaired_code_dir(session_id, round_num)

    @staticmethod
    def list_rounds(session_id: str) -> list[dict[str, Any]]:
        """List all rounds with metadata."""
        base = SessionService.session_dir(session_id)
        original = SessionService.original_dir(session_id)

        rounds = []

        # Round 0: original
        orig_count = sum(1 for f in original.rglob("*.py")) if original.exists() else 0
        rounds.append({"round": 0, "label": "Original", "files": orig_count})

        # Numbered rounds
        if base.exists():
            for d in sorted(base.iterdir()):
                if d.is_dir() and d.name.startswith("round_"):
                    num = int(d.name.split("_")[1])
                    code_dir = d / "repaired_code"
                    file_count = sum(1 for f in code_dir.rglob("*.py")) if code_dir.exists() else 0
                    has_findings = (d / "reports" / "findings.json").exists()
                    has_tests = (d / "generated_tests").exists() and any((d / "generated_tests").glob("*.py"))
                    rounds.append(
                        {
                            "round": num,
                            "label": f"Round {num}",
                            "files": file_count,
                            "has_findings": has_findings,
                            "has_tests": has_tests,
                        }
                    )

        return rounds

    # ── Backward compat aliases for versions/restore ──────

    @staticmethod
    def list_repair_rounds(session_id: str) -> list[dict[str, Any]]:
        """Alias for list_rounds (backward compat)."""
        return SessionService.list_rounds(session_id)

    @staticmethod
    def restore_repair_round(session_id: str, round_num: int) -> bool:
        """No-op in new layout. Code dirs are per-round, no 'active' to overwrite."""
        # In the new layout, there's nothing to restore. The caller should
        # just read from code_dir_for_round(session_id, round_num).
        return SessionService.code_dir_for_round(session_id, round_num).exists()

    @staticmethod
    def snapshot_workspace(session_id: str) -> int:
        """Backward compat: in new layout, next_round() is the snapshot."""
        return SessionService.next_round(session_id)

    # ── Session creation ──────────────────────────────────

    @staticmethod
    def create_session(source_type: str, github_url: str | None) -> str:
        session_id = str(uuid.uuid4())
        session_dir = SessionService.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        SessionService.original_dir(session_id).mkdir(parents=True, exist_ok=True)

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
        """List analyzable files from original/."""
        raw_dir = SessionService.original_dir(session_id)
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
        """List all sessions for the session picker."""
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

            has_analysis = (entry / "baseline_tests" / "reports" / "paper_metrics.json").exists()
            current_round = SessionService.current_round(session_id)
            has_tests = False
            if current_round > 0:
                tests_dir = entry / f"round_{current_round:02d}" / "generated_tests"
                has_tests = tests_dir.exists() and any(tests_dir.glob("*.py"))

            created = os.path.getmtime(session_json)

            sessions.append(
                {
                    "session_id": session_id,
                    "source_type": config.get("source_type", "unknown"),
                    "created_at": created,
                    "has_analysis": has_analysis,
                    "has_repair": current_round > 0,
                    "has_tests": has_tests,
                    "repair_rounds": current_round,
                }
            )

        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions

    @staticmethod
    def list_analysis_rounds(session_id: str) -> list[dict[str, Any]]:
        """List analysis findings across rounds."""
        rounds = []

        # Baseline
        baseline_findings = SessionService.baseline_reports_dir(session_id) / "findings.json"
        if baseline_findings.exists():
            findings = json.loads(baseline_findings.read_text(encoding="utf-8"))
            by_sev: dict[str, int] = {}
            for f in findings:
                sev = f.get("severity", "LOW")
                by_sev[sev] = by_sev.get(sev, 0) + 1
            rounds.append({"round": 0, "total": len(findings), "by_severity": by_sev})

        # Per-round
        base = SessionService.session_dir(session_id)
        for d in sorted(base.iterdir()) if base.exists() else []:
            if not d.is_dir() or not d.name.startswith("round_"):
                continue
            findings_path = d / "reports" / "findings.json"
            if not findings_path.exists():
                continue
            findings = json.loads(findings_path.read_text(encoding="utf-8"))
            by_sev = {}
            for f in findings:
                sev = f.get("severity", "LOW")
                by_sev[sev] = by_sev.get(sev, 0) + 1
            num = int(d.name.split("_")[1])
            rounds.append({"round": num, "total": len(findings), "by_severity": by_sev})

        return rounds
