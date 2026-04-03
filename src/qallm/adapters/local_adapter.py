from __future__ import annotations

from pathlib import Path

from qallm.adapters.base import InputAdapter
from qallm.adapters.helpers import copy_file_to_dir, copy_tree
from qallm.session.workspace import SessionService


class PythonFileAdapter(InputAdapter):
    def ingest(self, input_value: str) -> str:
        src = Path(input_value).expanduser().resolve()

        if not src.exists():
            raise FileNotFoundError(f"Python file not found: {src}")
        if not src.is_file() or src.suffix.lower() != ".py":
            raise ValueError(f"Expected a .py file, got: {src}")

        session_id = SessionService.create_session(
            source_type="python_file",
            github_url=None,
        )
        raw_dir = SessionService.workspace_raw_dir(session_id)
        copy_file_to_dir(src, raw_dir)
        return session_id


class PythonDirectoryAdapter(InputAdapter):
    def __init__(self, include_all_files: bool = True) -> None:
        self.include_all_files = include_all_files

    def ingest(self, input_value: str) -> str:
        src_dir = Path(input_value).expanduser().resolve()

        if not src_dir.exists():
            raise FileNotFoundError(f"Directory not found: {src_dir}")
        if not src_dir.is_dir():
            raise ValueError(f"Expected a directory, got: {src_dir}")

        session_id = SessionService.create_session(
            source_type="python_dir",
            github_url=None,
        )
        raw_dir = SessionService.workspace_raw_dir(session_id)

        if self.include_all_files:
            copy_tree(src_dir, raw_dir)
        else:
            copy_tree(src_dir, raw_dir, patterns=("*.py", "*.ipynb"))

        return session_id