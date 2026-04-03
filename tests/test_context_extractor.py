"""Tests for repair context extraction (QALLM-12)."""

from pathlib import Path

from qallm.repair.context_extractor import extract_function_context


def test_extracts_enclosing_function(tmp_path):
    src = tmp_path / "example.py"
    src.write_text(
        "import os\n"
        "\n"
        "def greet(name):\n"
        "    msg = f'Hello {name}'\n"
        "    eval(msg)\n"  # line 5 — finding
        "    return msg\n"
        "\n"
        "def other():\n"
        "    pass\n"
    )
    ctx, start = extract_function_context(src, line=5, padding=0)
    assert "def greet" in ctx
    assert "eval(msg)" in ctx
    assert "def other" not in ctx


def test_includes_padding(tmp_path):
    src = tmp_path / "example.py"
    src.write_text(
        "import os\n"
        "\n"
        "def greet(name):\n"
        "    eval(name)\n"  # line 4
        "    return name\n"
    )
    ctx, start = extract_function_context(src, line=4, padding=2)
    # padding=2 should include lines before the function
    assert "import os" in ctx


def test_fallback_on_no_line(tmp_path):
    src = tmp_path / "example.py"
    src.write_text("x = 1\ny = 2\n")
    ctx, start = extract_function_context(src, line=None)
    assert "x = 1" in ctx
    assert start == 1


def test_fallback_on_syntax_error(tmp_path):
    src = tmp_path / "broken.py"
    src.write_text("def foo(\n   broken syntax here\n   x = eval('1')\n")
    ctx, start = extract_function_context(src, line=3)
    # Should fall back to window approach, not crash
    assert "eval" in ctx


def test_missing_file():
    ctx, start = extract_function_context(Path("/nonexistent.py"), line=5)
    assert ctx == ""
    assert start == 1
