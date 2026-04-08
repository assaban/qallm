from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qallm.main import app
from qallm.session.config import settings


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Give every test its own isolated DATA_DIR.

    This patches the already imported settings object directly, which is more
    reliable than only setting os.environ after imports have happened.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    yield data_dir

    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def client() -> TestClient:
    """Shared TestClient for integration tests."""
    return TestClient(app)


@pytest.fixture
def sample_zip() -> bytes:
    """Create an in memory zip containing a small Python project."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("sample/hello.py", 'import os\npassword = "secret123"\nprint(password)\n')
        zf.writestr("sample/util.py", "def add(a, b):\n    return a + b\n")
    return buf.getvalue()