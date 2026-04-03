from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from qallm.session.config import settings


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Give every test its own isolated DATA_DIR.

    This patches the already-imported settings object directly, which is more
    reliable than only setting os.environ after imports have happened.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))

    yield data_dir

    shutil.rmtree(data_dir, ignore_errors=True)