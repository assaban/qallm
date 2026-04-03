from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile

from qallm.adapters.detector import InputKind, detect_input
from qallm.adapters.factory import AdapterFactory
from qallm.adapters.notebook import extract_notebook_to_python


class IngestService:
    """Shared orchestration layer for CLI, web, and future Jupyter entry points."""

    @staticmethod
    def create_session_from_input(input_value: str) -> str:
        detected = detect_input(input_value)
        adapter = AdapterFactory.create(detected.kind)
        session_id = adapter.ingest(detected.value)

        if detected.kind in {
            InputKind.NOTEBOOK,
            InputKind.ZIP_ARCHIVE,
            InputKind.PYTHON_DIR,
            InputKind.GIT_URL,
        }:
            IngestService.materialize_notebooks(session_id)

        return session_id

    @staticmethod
    def create_session_from_upload(archive: UploadFile) -> str:
        filename = archive.filename or "upload.zip"
        suffix = Path(filename).suffix.lower()

        if suffix != ".zip":
            raise ValueError("Only .zip uploads are supported.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            shutil.copyfileobj(archive.file, tmp)
            temp_zip_path = Path(tmp.name)

        try:
            session_id = IngestService.create_session_from_input(str(temp_zip_path))
        finally:
            try:
                temp_zip_path.unlink()
            except OSError:
                pass

        return session_id

    @staticmethod
    def create_session_from_git(git_url: str) -> str:
        session_id = IngestService.create_session_from_input(git_url)
        return session_id

    @staticmethod
    def materialize_notebooks(session_id: str) -> None:
        from qallm.session.workspace import SessionService

        raw_dir = SessionService.workspace_raw_dir(session_id)
        extracted_dir = raw_dir / "_extracted_notebooks"
        extracted_dir.mkdir(parents=True, exist_ok=True)

        for notebook_path in raw_dir.rglob("*.ipynb"):
            extract_notebook_to_python(notebook_path, extracted_dir)
