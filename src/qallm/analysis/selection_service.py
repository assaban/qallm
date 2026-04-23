from __future__ import annotations

import shutil

from qallm.session.workspace import SessionService


class SelectionService:
    @staticmethod
    def apply_selection(session_id: str, selected_files: list[str]) -> dict:
        """Copy selected files from workspace_raw → workspace (active).

        Only resets workspace from raw if NO repair has occurred yet.
        After repair, the active workspace already contains repaired code
        and should not be overwritten.
        """
        raw = SessionService.workspace_raw_dir(session_id)
        active = SessionService.workspace_active_dir(session_id)

        if not raw.exists():
            return {
                "ok": False,
                "error": "workspace_raw not found",
                "raw_dir": str(raw),
            }

        # Check if repairs have been done
        history = SessionService.repair_history_dir(session_id)
        has_repairs = history.exists() and any(history.iterdir())

        if has_repairs:
            # Workspace has repaired code; do NOT reset from raw
            active_root = active.resolve()
            present = 0
            missing_files: list[str] = []
            for rel in selected_files or []:
                rel_norm = rel.lstrip("./")
                if (active_root / rel_norm).exists():
                    present += 1
                else:
                    missing_files.append(rel)
            return {
                "ok": True,
                "copied": 0,
                "skipped": len(missing_files),
                "missing": missing_files[:50],
                "rejected": [],
                "active_file_count": sum(1 for p in active_root.rglob("*") if p.is_file()),
                "note": "Preserved repaired workspace",
            }

        # No repairs yet: reset workspace from raw
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
