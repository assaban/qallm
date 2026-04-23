"""Selection service: copies selected files to the working directory for analysis.

In the round-based layout:
  - Before any repair: copies from original/ (no round exists yet)
  - After repair: reads from round_NN/repaired_code/ (no copy needed)
"""

from __future__ import annotations

from qallm.session.workspace import SessionService


class SelectionService:
    @staticmethod
    def apply_selection(session_id: str, selected_files: list[str]) -> dict:
        """Ensure selected files exist in the current code directory.

        In the round-based layout, there is no separate 'active workspace' to
        copy into. The code directory for each round is already set.

        This method now validates that the selected files exist in the
        appropriate directory and returns file counts.
        """
        current_round = SessionService.current_round(session_id)
        code_dir = SessionService.code_dir_for_round(session_id, current_round)

        if not code_dir.exists():
            return {
                "ok": False,
                "error": f"Code directory not found: {code_dir}",
            }

        present = 0
        missing: list[str] = []

        for rel in selected_files or []:
            rel_norm = rel.lstrip("./")
            if (code_dir / rel_norm).exists():
                present += 1
            else:
                missing.append(rel)

        file_count = sum(1 for p in code_dir.rglob("*") if p.is_file())

        return {
            "ok": True,
            "copied": 0,
            "skipped": len(missing),
            "missing": missing[:50],
            "rejected": [],
            "active_file_count": file_count,
            "code_dir": str(code_dir),
            "round": current_round,
        }
