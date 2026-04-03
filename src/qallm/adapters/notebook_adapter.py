from __future__ import annotations

from pathlib import Path

from qallm.adapters.base import InputAdapter
from qallm.adapters.helpers import copy_file_to_dir
from qallm.session.workspace import SessionService


class NotebookFileAdapter(InputAdapter):
    def ingest(self, input_value: str) -> str:
        src = Path(input_value).expanduser().resolve()

        if not src.exists():
            raise FileNotFoundError(f"Notebook file not found: {src}")
        if not src.is_file() or src.suffix.lower() != ".ipynb":
            raise ValueError(f"Expected a .ipynb file, got: {src}")

        session_id = SessionService.create_session(
            source_type="notebook",
            github_url=None,
        )
        raw_dir = SessionService.workspace_raw_dir(session_id)
        copy_file_to_dir(src, raw_dir)
        return session_id