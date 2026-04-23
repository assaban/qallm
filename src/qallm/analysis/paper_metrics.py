"""Compute quality metrics matching the Islam et al. paper (Table 5/6).

Metrics:
  CS   : Code Smells (count of Ruff findings)
  MI   : Maintainability Index (via radon mi)
  CoDu : Code Duplication percentage (line-based)
  CoDe : Comment Density percentage
  LoC  : Lines of Code
  CC   : Cyclomatic Complexity average (via radon cc)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from qallm.session.workspace import SessionService


def compute_paper_metrics(session_id: str) -> dict[str, Any]:
    """Compute all 6 paper metrics for the active workspace."""
    workspace = SessionService.workspace_active_dir(session_id)
    if not workspace.exists():
        workspace = SessionService.workspace_raw_dir(session_id)

    py_files = list(workspace.rglob("*.py"))
    if not py_files:
        return {"cs": 0, "mi": 0.0, "codu": 0.0, "code": 0.0, "loc": 0, "cc": 0.0, "files": 0, "per_file": []}

    total_loc = 0
    total_comments = 0
    per_file = []

    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = source.splitlines()
        loc = len(lines)
        total_loc += loc
        comment_lines = sum(1 for ln in lines if ln.strip().startswith("#"))
        total_comments += comment_lines
        code_lines = loc - comment_lines - sum(1 for ln in lines if not ln.strip())

        per_file.append(
            {
                "file": pf.relative_to(workspace).as_posix(),
                "loc": loc,
                "comment_lines": comment_lines,
                "code_lines": code_lines,
            }
        )

    code_pct = (total_comments / total_loc * 100) if total_loc > 0 else 0.0
    codu = _compute_duplication(py_files)
    cc_avg = _radon_cc(workspace)
    mi_avg = _radon_mi(workspace)
    cs_count = _count_code_smells(workspace)

    result = {
        "cs": cs_count,
        "mi": round(mi_avg, 2),
        "codu": round(codu, 2),
        "code": round(code_pct, 2),
        "loc": total_loc,
        "cc": round(cc_avg, 2),
        "files": len(py_files),
        "per_file": per_file,
    }

    reports = SessionService.reports_dir(session_id)
    reports.mkdir(parents=True, exist_ok=True)

    existing = sorted(reports.glob("paper_metrics_round_*.json"))
    next_round = len(existing) + 1
    (reports / f"paper_metrics_round_{next_round:02d}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (reports / "paper_metrics_latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def get_paper_metrics_history(session_id: str) -> list[dict[str, Any]]:
    """Return all paper metrics rounds for a session."""
    reports = SessionService.reports_dir(session_id)
    rounds = []
    for path in sorted(reports.glob("paper_metrics_round_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        num = int(path.stem.split("_")[-1])
        data["round"] = num
        rounds.append(data)
    return rounds


def _radon_cc(workspace: Path) -> float:
    if not shutil.which("radon"):
        return 0.0
    try:
        r = subprocess.run(
            ["radon", "cc", ".", "-j", "-a"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        all_cc = []
        for file_blocks in data.values():
            if isinstance(file_blocks, list):
                for block in file_blocks:
                    if isinstance(block, dict) and "complexity" in block:
                        all_cc.append(block["complexity"])
        return sum(all_cc) / len(all_cc) if all_cc else 0.0
    except Exception:
        return 0.0


def _radon_mi(workspace: Path) -> float:
    if not shutil.which("radon"):
        return 0.0
    try:
        r = subprocess.run(
            ["radon", "mi", ".", "-j"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        scores = []
        for val in data.values():
            if isinstance(val, dict) and "mi" in val:
                scores.append(val["mi"])
            elif isinstance(val, (int, float)):
                scores.append(float(val))
        return sum(scores) / len(scores) if scores else 0.0
    except Exception:
        return 0.0


def _count_code_smells(workspace: Path) -> int:
    if not shutil.which("ruff"):
        return 0
    try:
        r = subprocess.run(
            ["ruff", "check", ".", "--output-format=json", "--quiet"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(r.stdout) if r.stdout.strip() else []
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def _compute_duplication(py_files: list[Path], min_lines: int = 4) -> float:
    total_lines = 0
    line_blocks: dict[str, int] = {}

    for pf in py_files:
        try:
            lines = pf.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        stripped = [ln.strip() for ln in lines]
        total_lines += len(stripped)

        for i in range(len(stripped) - min_lines + 1):
            block = "\n".join(stripped[i : i + min_lines])
            if block.strip():
                line_blocks[block] = line_blocks.get(block, 0) + 1

    dup_lines = 0
    for block, count in line_blocks.items():
        if count > 1:
            dup_lines += min_lines * count

    return (dup_lines / total_lines * 100) if total_lines > 0 else 0.0
