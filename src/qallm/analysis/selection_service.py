from __future__ import annotations

import shutil

from qallm.session.workspace import SessionService


class SelectionService:
    @staticmethod
    def apply_selection(session_id: str, selected_files: list[str]) -> dict:
        """Copy only the selected files from workspace_raw → workspace (active)."""
        raw = SessionService.workspace_raw_dir(session_id)
        active = SessionService.workspace_active_dir(session_id)

        if not raw.exists():
            return {
                "ok": False,
                "error": "workspace_raw not found",
                "raw_dir": str(raw),
            }

        # Reset active workspace
        try:
            shutil.rmtree(active, ignore_errors=True)
            active.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {
                "ok": False,
                "error": f"Failed to reset active workspace: {e}",
                "active_dir": str(active),
            }

        copied = 0
        skipped = 0
        missing: list[str] = []
        rejected: list[str] = []

        raw_root = raw.resolve()
        active_root = active.resolve()

        for rel in selected_files or []:
            rel_norm = rel.lstrip("./")
            src = (raw_root / rel_norm).resolve()

            # Security: ensure src stays within raw workspace
            if raw_root != src and raw_root not in src.parents:
                rejected.append(rel)
                skipped += 1
                continue

            if not src.exists() or not src.is_file():
                missing.append(rel)
                skipped += 1
                continue

            dst = active_root / rel_norm
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                missing.append(f"{rel} (copy failed: {e})")
                skipped += 1

        file_count = sum(1 for p in active_root.rglob("*") if p.is_file())

        return {
            "ok": True,
            "copied": copied,
            "skipped": skipped,
            "missing": missing[:50],
            "rejected": rejected[:50],
            "active_file_count": file_count,
        }
