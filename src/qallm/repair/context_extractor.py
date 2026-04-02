"""Extract surrounding function / class context for a finding.

Strategy: given a file and line number, walk outward to find the
enclosing function or class definition and return the complete
block (plus a few lines of padding) so the LLM has enough context
to generate a correct patch.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _find_enclosing_node(
    tree: ast.Module,
    target_line: int,
) -> ast.AST | None:
    """Return the innermost function/class containing *target_line*."""
    best: ast.AST | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= target_line <= (node.end_lineno or node.lineno):
                    if best is None or node.lineno >= getattr(best, "lineno", 0):
                        best = node
    return best


def extract_function_context(
    filepath: Path,
    line: int | None,
    padding: int = 3,
) -> tuple[str, int]:
    """Return (context_text, start_line) for the enclosing function/class.

    If parsing fails or no enclosing node is found, falls back to a
    window of ±30 lines around the target line.

    Parameters
    ----------
    filepath : Path
        Absolute or relative path to the source file.
    line : int | None
        1-indexed line number of the finding.
    padding : int
        Extra lines above/below the enclosing node.

    Returns
    -------
    tuple[str, int]
        (code_context, first_line_number)
    """
    if not filepath.exists():
        return "", 1

    source = filepath.read_text(encoding="utf-8", errors="replace")
    all_lines = source.splitlines()
    total = len(all_lines)

    if not line or line < 1:
        # No line info — return the whole file (capped)
        cap = min(total, 120)
        return "\n".join(all_lines[:cap]), 1

    # Try AST-based extraction
    try:
        tree = ast.parse(source)
        node = _find_enclosing_node(tree, line)
        if node is not None:
            start = max(1, getattr(node, "lineno", line) - padding)
            end = min(total, getattr(node, "end_lineno", line) + padding)
            return "\n".join(all_lines[start - 1 : end]), start
    except SyntaxError:
        pass

    # Fallback: window around the target line
    window = 30
    start = max(1, line - window)
    end = min(total, line + window)
    return "\n".join(all_lines[start - 1 : end]), start
