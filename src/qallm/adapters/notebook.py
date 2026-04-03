"""Jupyter notebook adapter — extract code cells from .ipynb files.

This module parses .ipynb JSON files, extracts code cells, strips
Jupyter-specific magic commands, and produces Python source files
ready for the analysis pipeline.

"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedNotebook:
    source_notebook: Path
    generated_python: Path
    cell_map_path: Path


def is_notebook(path: Path) -> bool:
    """Check if a file is a Jupyter notebook."""
    return path.suffix == ".ipynb"


def strip_magic(line: str) -> str | None:
    stripped = line.lstrip()
    if stripped.startswith("%") or stripped.startswith("!"):
        return None
    return line


def extract_notebook_to_python(notebook_path: Path, output_dir: Path) -> ExtractedNotebook:
    """Extract code cells from a Jupyter notebook into a generated Python file.

    Returns:
        ExtractedNotebook:
            - source_notebook: original .ipynb path
            - generated_python: extracted .py file path
            - cell_map_path: JSON mapping from generated lines back to notebook cells
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(notebook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed notebook JSON: {notebook_path}") from exc

    lines: list[str] = []
    cell_map: list[dict] = []
    generated_line = 1

    for idx, cell in enumerate(data.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        src = cell.get("source", [])
        src_lines = src.splitlines(keepends=True) if isinstance(src, str) else list(src)

        cleaned: list[str] = []
        skipped_magic: list[str] = []

        for raw in src_lines:
            maybe = strip_magic(raw)
            if maybe is None:
                skipped_magic.append(raw.rstrip("\n"))
                continue
            cleaned.append(maybe)

        if not cleaned:
            continue

        lines.append(f"# --- cell {idx} ---\n")
        start_line = generated_line + 1
        lines.extend(cleaned)

        if cleaned and not cleaned[-1].endswith("\n"):
            lines.append("\n")

        lines.append("\n")
        end_line = start_line + len(cleaned) - 1

        cell_map.append(
            {
                "cell_index": idx,
                "generated_start_line": start_line,
                "generated_end_line": end_line,
                "skipped_magic": skipped_magic,
            }
        )

        generated_line = len(lines) + 1

    py_path = output_dir / f"{notebook_path.stem}.extracted.py"
    py_path.write_text("".join(lines), encoding="utf-8")

    cell_map_path = output_dir / f"{notebook_path.stem}.cell_map.json"
    cell_map_path.write_text(json.dumps(cell_map, indent=2), encoding="utf-8")

    return ExtractedNotebook(
        source_notebook=notebook_path,
        generated_python=py_path,
        cell_map_path=cell_map_path,
    )