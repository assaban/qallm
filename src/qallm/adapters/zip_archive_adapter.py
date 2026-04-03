from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from qallm.adapters.base import InputAdapter
from qallm.session.workspace import SessionService


class ZipArchiveAdapter(InputAdapter):
    """Ingest a local ZIP archive into a QALLM session workspace."""

    JUNK_NAMES = {"__MACOSX", ".DS_Store"}

    def ingest(self, input_value: str) -> str:
        archive_path = Path(input_value).expanduser().resolve()

        if not archive_path.exists():
            raise FileNotFoundError(f"ZIP archive not found: {archive_path}")
        if not archive_path.is_file() or archive_path.suffix.lower() != ".zip":
            raise ValueError(f"Expected a .zip file, got: {archive_path}")

        session_id = SessionService.create_session(
            source_type="zip",
            github_url=None,
        )
        raw_dir = SessionService.workspace_raw_dir(session_id)
        raw_dir.mkdir(parents=True, exist_ok=True)

        self._safe_extract_zip(archive_path, raw_dir)
        self._clean_workspace(raw_dir)
        return session_id

    @classmethod
    def _safe_extract_zip(cls, archive_path: Path, target_dir: Path) -> None:
        target_dir = target_dir.resolve()

        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue

                filename = member.filename
                basename = Path(filename).name

                if basename in cls.JUNK_NAMES or basename.startswith("._"):
                    continue

                resolved_target = (target_dir / filename).resolve()
                if not str(resolved_target).startswith(str(target_dir)):
                    raise ValueError(f"Unsafe ZIP member path detected: {filename}")

                resolved_target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(resolved_target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    @classmethod
    def _clean_workspace(cls, raw_dir: Path) -> None:
        """Remove junk files and directories that may interfere with tooling."""
        for path in list(raw_dir.rglob("*")):
            if path.name in cls.JUNK_NAMES:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    try:
                        path.unlink()
                    except OSError:
                        pass

        for path in list(raw_dir.rglob("._*")):
            try:
                path.unlink()
            except OSError:
                pass