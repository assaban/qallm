"""Regression tests for normalizer path utilities."""

from pathlib import Path

from qallm.analysis.normalizers.util import get_rel_path


def test_relative_path_stripped(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    assert get_rel_path(ws, "./demo/domain.py") == "demo/domain.py"


def test_absolute_path_inside_workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "demo").mkdir()
    (ws / "demo" / "domain.py").write_text("x = 1")

    abs_path = str(ws.resolve() / "demo" / "domain.py")
    assert get_rel_path(ws, abs_path) == "demo/domain.py"


def test_absolute_container_path(tmp_path):
    """Reproduces the ruff bug: /app/data/{sid}/workspace/demo/domain.py"""
    ws = tmp_path / "data" / "abc123" / "workspace"
    ws.mkdir(parents=True)
    (ws / "demo").mkdir()
    (ws / "demo" / "domain.py").write_text("x = 1")

    abs_path = str(ws.resolve() / "demo" / "domain.py")
    result = get_rel_path(ws, abs_path)
    assert result == "demo/domain.py", f"Expected 'demo/domain.py', got '{result}'"


def test_empty_filename():
    assert get_rel_path(Path("/tmp"), "") == ""


def test_bare_filename(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    assert get_rel_path(ws, "hello.py") == "hello.py"
