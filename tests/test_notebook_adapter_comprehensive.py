"""Comprehensive tests for the Jupyter notebook adapter (T-012).

Covers: valid notebooks, empty notebooks, empty code cells, markdown only,
magic command stripping, malformed JSON, cell map line tracking,
multi cell ordering, and source format variants (string vs list).
"""

import json
from pathlib import Path

import pytest

from qallm.adapters.notebook import (
    ExtractedNotebook,
    extract_notebook_to_python,
    is_notebook,
    strip_magic,
)

# -- is_notebook


def test_is_notebook_true_for_ipynb():
    assert is_notebook(Path("analysis.ipynb")) is True


def test_is_notebook_false_for_py():
    assert is_notebook(Path("script.py")) is False


def test_is_notebook_false_for_no_extension():
    assert is_notebook(Path("README")) is False


# -- strip_magic


def test_strip_magic_removes_percent_magic():
    assert strip_magic("%matplotlib inline\n") is None


def test_strip_magic_removes_bang_command():
    assert strip_magic("!pip install pandas\n") is None


def test_strip_magic_keeps_normal_code():
    assert strip_magic("x = 1\n") == "x = 1\n"


def test_strip_magic_handles_indented_magic():
    assert strip_magic("  %timeit sum(range(100))") is None


def test_strip_magic_keeps_modulo_in_expression():
    assert strip_magic("result = 10 % 3\n") == "result = 10 % 3\n"


def test_strip_magic_keeps_string_with_exclamation():
    assert strip_magic('msg = "Hello!"\n') == 'msg = "Hello!"\n'


# -- extract_notebook_to_python: valid notebooks


def test_extract_basic_notebook(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["x = 1\n", "y = 2\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "basic.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")

    assert isinstance(result, ExtractedNotebook)
    assert result.generated_python.exists()
    assert result.cell_map_path.exists()
    assert result.source_notebook == nb_path

    content = result.generated_python.read_text(encoding="utf-8")
    assert "x = 1" in content
    assert "y = 2" in content


def test_extract_preserves_cell_order(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["first = 1\n"]},
            {"cell_type": "markdown", "source": ["# Divider\n"]},
            {"cell_type": "code", "source": ["second = 2\n"]},
            {"cell_type": "code", "source": ["third = 3\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "order.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    content = result.generated_python.read_text(encoding="utf-8")

    pos_first = content.index("first = 1")
    pos_second = content.index("second = 2")
    pos_third = content.index("third = 3")
    assert pos_first < pos_second < pos_third


def test_extract_source_as_single_string(tmp_path: Path):
    """Notebooks can store cell source as a single string instead of a list."""
    notebook = {
        "cells": [
            {"cell_type": "code", "source": "x = 1\ny = 2\n"},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "string_source.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    content = result.generated_python.read_text(encoding="utf-8")
    assert "x = 1" in content
    assert "y = 2" in content


# -- extract_notebook_to_python: edge cases


def test_extract_empty_notebook_no_cells(tmp_path: Path):
    notebook = {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    nb_path = tmp_path / "empty.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    assert result.generated_python.read_text(encoding="utf-8") == ""

    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))
    assert cell_map == []


def test_extract_notebook_missing_cells_key(tmp_path: Path):
    """A notebook JSON without a 'cells' key should produce empty output."""
    notebook = {"metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    nb_path = tmp_path / "no_cells.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    assert result.generated_python.read_text(encoding="utf-8") == ""


def test_extract_notebook_empty_code_cell(tmp_path: Path):
    """A code cell with no source lines should be skipped."""
    notebook = {
        "cells": [
            {"cell_type": "code", "source": []},
            {"cell_type": "code", "source": ["valid = True\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "empty_cell.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    content = result.generated_python.read_text(encoding="utf-8")

    assert "valid = True" in content
    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))
    assert len(cell_map) == 1
    assert cell_map[0]["cell_index"] == 1


def test_extract_notebook_code_cell_only_magic(tmp_path: Path):
    """A code cell that contains only magic commands should be skipped."""
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["%matplotlib inline\n", "!pip install x\n"]},
            {"cell_type": "code", "source": ["real_code = 42\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "only_magic.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))
    assert len(cell_map) == 1
    assert cell_map[0]["cell_index"] == 1


def test_extract_malformed_json_raises(tmp_path: Path):
    nb_path = tmp_path / "bad.ipynb"
    nb_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed notebook JSON"):
        extract_notebook_to_python(nb_path, tmp_path / "out")


# -- cell map accuracy


def test_cell_map_tracks_line_numbers(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["a = 1\n", "b = 2\n"]},
            {"cell_type": "code", "source": ["c = 3\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "lines.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))

    assert len(cell_map) == 2

    first = cell_map[0]
    assert first["cell_index"] == 0
    assert first["generated_start_line"] >= 1
    assert first["generated_end_line"] >= first["generated_start_line"]

    second = cell_map[1]
    assert second["cell_index"] == 1
    assert second["generated_start_line"] > first["generated_end_line"]


def test_cell_map_records_skipped_magic(tmp_path: Path):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["%load_ext autoreload\n", "%autoreload 2\n", "x = 1\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "magic.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")
    cell_map = json.loads(result.cell_map_path.read_text(encoding="utf-8"))

    assert len(cell_map[0]["skipped_magic"]) == 2
    assert "%load_ext autoreload" in cell_map[0]["skipped_magic"]
    assert "%autoreload 2" in cell_map[0]["skipped_magic"]


# -- output file naming


def test_output_files_use_notebook_stem(tmp_path: Path):
    notebook = {
        "cells": [{"cell_type": "code", "source": ["x = 1\n"]}],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    nb_path = tmp_path / "my_analysis.ipynb"
    nb_path.write_text(json.dumps(notebook), encoding="utf-8")

    result = extract_notebook_to_python(nb_path, tmp_path / "out")

    assert result.generated_python.name == "my_analysis.extracted.py"
    assert result.cell_map_path.name == "my_analysis.cell_map.json"
