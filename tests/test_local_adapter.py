"""Tests for local file and directory adapters (T-012)."""

from pathlib import Path

import pytest

from qallm.adapters.local_adapter import PythonDirectoryAdapter, PythonFileAdapter
from qallm.session.workspace import SessionService


# -- PythonFileAdapter


class TestPythonFileAdapter:
    def test_ingest_creates_session_with_file(self, tmp_path: Path):
        src = tmp_path / "hello.py"
        src.write_text("print('hello')\n", encoding="utf-8")

        adapter = PythonFileAdapter()
        session_id = adapter.ingest(str(src))

        assert SessionService.session_exists(session_id)
        files = SessionService.list_workspace_files(session_id)
        assert "hello.py" in files

    def test_ingest_rejects_nonexistent_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            PythonFileAdapter().ingest(str(tmp_path / "ghost.py"))

    def test_ingest_rejects_non_python_file(self, tmp_path: Path):
        src = tmp_path / "data.csv"
        src.write_text("a,b,c\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Expected a .py file"):
            PythonFileAdapter().ingest(str(src))

    def test_ingest_rejects_directory(self, tmp_path: Path):
        d = tmp_path / "pkg"
        d.mkdir()

        with pytest.raises(ValueError, match="Expected a .py file"):
            PythonFileAdapter().ingest(str(d))


# -- PythonDirectoryAdapter


class TestPythonDirectoryAdapter:
    def test_ingest_copies_all_files(self, tmp_path: Path):
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        (src_dir / "util.py").write_text("y = 2\n", encoding="utf-8")
        (src_dir / "README.md").write_text("# Docs\n", encoding="utf-8")

        adapter = PythonDirectoryAdapter(include_all_files=True)
        session_id = adapter.ingest(str(src_dir))

        # list_workspace_files only returns analyzable suffixes (.py, .ipynb)
        files = SessionService.list_workspace_files(session_id)
        assert "main.py" in files
        assert "util.py" in files

        # but the non analyzable file should still exist on disk
        raw_dir = SessionService.workspace_raw_dir(session_id)
        assert (raw_dir / "README.md").exists()

    def test_ingest_with_pattern_filter(self, tmp_path: Path):
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        (src_dir / "data.csv").write_text("a,b\n", encoding="utf-8")

        adapter = PythonDirectoryAdapter(include_all_files=False)
        session_id = adapter.ingest(str(src_dir))

        files = SessionService.list_workspace_files(session_id)
        assert "main.py" in files
        assert "data.csv" not in files

    def test_ingest_preserves_subdirectory_structure(self, tmp_path: Path):
        src_dir = tmp_path / "project"
        (src_dir / "pkg").mkdir(parents=True)
        (src_dir / "pkg" / "mod.py").write_text("z = 3\n", encoding="utf-8")

        adapter = PythonDirectoryAdapter()
        session_id = adapter.ingest(str(src_dir))

        files = SessionService.list_workspace_files(session_id)
        assert "pkg/mod.py" in files

    def test_ingest_rejects_nonexistent_directory(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            PythonDirectoryAdapter().ingest(str(tmp_path / "nonexistent"))

    def test_ingest_rejects_file_instead_of_directory(self, tmp_path: Path):
        f = tmp_path / "file.py"
        f.write_text("x = 1\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Expected a directory"):
            PythonDirectoryAdapter().ingest(str(f))
