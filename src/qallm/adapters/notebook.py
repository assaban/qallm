"""Jupyter notebook adapter — extract code cells from .ipynb files.

This module parses .ipynb JSON files, extracts code cells, strips
Jupyter-specific magic commands, and produces Python source files
ready for the analysis pipeline.

Status: PLACEHOLDER — implementation is thesis backlog item T-008.
"""

from __future__ import annotations

from pathlib import Path


def is_notebook(path: Path) -> bool:
    """Check if a file is a Jupyter notebook."""
    return path.suffix == ".ipynb"


def extract_code_cells(notebook_path: Path) -> list[dict]:
    """Extract code cells from a Jupyter notebook.

    Returns a list of dicts, each containing:
        - cell_index: int (0-based position in the notebook)
        - source: str (the Python code)
        - line_offset: int (cumulative line count for mapping findings back)

    TODO (T-008): Implement full extraction with magic command stripping.
    """
    raise NotImplementedError("Jupyter adapter not yet implemented — see backlog T-008")
