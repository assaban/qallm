import json
import zipfile
from pathlib import Path

from qallm.services.ingest_service import IngestService
from qallm.session.workspace import SessionService


def test_create_session_from_input_with_python_file(tmp_path: Path):
    src = tmp_path / "demo.py"
    src.write_text("print('hello')\n", encoding="utf-8")

    session_id = IngestService.create_session_from_input(str(src))

    raw_dir = SessionService.workspace_raw_dir(session_id)
    assert (raw_dir / "demo.py").exists()


def test_create_session_from_input_with_notebook_materializes_python(tmp_path: Path):
    notebook_path = tmp_path / "demo.ipynb"
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["x = 1\n", "print(x)\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    notebook_path.write_text(json.dumps(notebook), encoding="utf-8")

    session_id = IngestService.create_session_from_input(str(notebook_path))

    raw_dir = SessionService.workspace_raw_dir(session_id)
    extracted = raw_dir / "_extracted_notebooks" / "demo.extracted.py"

    assert (raw_dir / "demo.ipynb").exists()
    assert extracted.exists()
    assert "x = 1" in extracted.read_text(encoding="utf-8")


def test_create_session_from_input_with_zip_materializes_nested_notebooks(tmp_path: Path):
    archive = tmp_path / "project.zip"
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["y = 2\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/demo.ipynb", json.dumps(notebook))
        zf.writestr("pkg/module.py", "print('hi')\n")

    session_id = IngestService.create_session_from_input(str(archive))

    raw_dir = SessionService.workspace_raw_dir(session_id)
    assert (raw_dir / "nested" / "demo.ipynb").exists()
    assert (raw_dir / "pkg" / "module.py").exists()

    extracted = raw_dir / "_extracted_notebooks" / "demo.extracted.py"
    assert extracted.exists()
    assert "y = 2" in extracted.read_text(encoding="utf-8")