"""Tests for normalizer utility helpers: get_rel_path and get_snippet."""

from pathlib import Path

from qallm.analysis.normalizers.util import get_rel_path, get_snippet

# ---------------------------------------------------------------------------
# get_rel_path
# ---------------------------------------------------------------------------


def test_get_rel_path_absolute_inside_workspace(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    abs_path = str(ws / "src" / "foo.py")
    result = get_rel_path(ws, abs_path)
    assert result == "src/foo.py"


def test_get_rel_path_dot_prefix(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    result = get_rel_path(ws, "./foo.py")
    assert result == "foo.py"


def test_get_rel_path_empty_string(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    assert get_rel_path(ws, "") == ""


def test_get_rel_path_plain_relative(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    result = get_rel_path(ws, "subdir/bar.py")
    assert result == "subdir/bar.py"


# ---------------------------------------------------------------------------
# get_snippet
# ---------------------------------------------------------------------------


def test_get_snippet_marks_target_line(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "demo.py").write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")
    snippet = get_snippet(ws, "demo.py", line=3)
    assert snippet is not None
    assert ">> " in snippet
    # target line should be marked
    assert ">>    3: line3" in snippet


def test_get_snippet_includes_context_lines(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "demo.py").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    snippet = get_snippet(ws, "demo.py", line=3, context=2)
    assert snippet is not None
    # should include lines 1-5
    assert "1: a" in snippet
    assert "5: e" in snippet


def test_get_snippet_missing_file_returns_none(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert get_snippet(ws, "nonexistent.py", line=1) is None


def test_get_snippet_none_line_returns_none(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "demo.py").write_text("x = 1\n", encoding="utf-8")
    assert get_snippet(ws, "demo.py", line=None) is None
