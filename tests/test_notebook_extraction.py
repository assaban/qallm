import json
from pathlib import Path

from qallm.adapters.notebook import extract_notebook_to_python


def test_extract_notebook_to_python_strips_magic_and_creates_cell_map(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Title\n"]},
            {"cell_type": "code", "source": ["%matplotlib inline\n", "x = 1\n", "print(x)\n"]},
            {"cell_type": "code", "source": ["!pip install pandas\n", "y = 2\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    notebook_path = tmp_path / "demo.ipynb"
    notebook_path.write_text(json.dumps(notebook), encoding="utf-8")

    out_dir = tmp_path / "out"
    result = extract_notebook_to_python(notebook_path, out_dir)

    generated = result.generated_python.read_text(encoding="utf-8")
    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))

    assert "x = 1" in generated
    assert "print(x)" in generated
    assert "y = 2" in generated
    assert "%matplotlib inline" not in generated
    assert "!pip install pandas" not in generated

    assert len(cell_map) == 2
    assert cell_map[0]["cell_index"] == 1
    assert cell_map[1]["cell_index"] == 2
    assert "%matplotlib inline" in cell_map[0]["skipped_magic"]
    assert "!pip install pandas" in cell_map[1]["skipped_magic"]


def test_extract_notebook_with_only_markdown_creates_empty_python_file(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Only prose\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    notebook_path = tmp_path / "empty.ipynb"
    notebook_path.write_text(json.dumps(notebook), encoding="utf-8")

    out_dir = tmp_path / "out"
    result = extract_notebook_to_python(notebook_path, out_dir)

    assert result.generated_python.exists()
    assert result.generated_python.read_text(encoding="utf-8") == ""

    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))
    assert cell_map == []