import io
import json
import zipfile

from fastapi.testclient import TestClient

from qallm.main import app


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_upload_zip_creates_session_and_lists_files():
    client = TestClient(app)

    notebook = {
        "cells": [{"cell_type": "code", "source": ["x = 1\n"]}],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    archive_bytes = _zip_bytes(
        {
            "demo.py": "print('hello')\n",
            "nb/demo.ipynb": json.dumps(notebook),
        }
    )

    response = client.post(
        "/api/session/upload",
        files={"archive": ("source.zip", archive_bytes, "application/zip")},
    )

    assert response.status_code == 200
    session_id = response.json()["session_id"]

    files_response = client.get(f"/api/session/{session_id}/files")
    assert files_response.status_code == 200

    files = files_response.json()["files"]
    assert "demo.py" in files
    assert "nb/demo.ipynb" in files


def test_upload_rejects_non_zip():
    client = TestClient(app)

    response = client.post(
        "/api/session/upload",
        files={"archive": ("bad.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert "Only .zip uploads are supported" in response.json()["detail"]