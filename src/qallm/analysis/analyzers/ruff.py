from __future__ import annotations

import shutil
from pathlib import Path

from qallm.analysis.util import run_cmd

from .base import RawToolResult, StaticCodeAnalyzer


class RuffAnalyzer(StaticCodeAnalyzer):
    def tool_name(self) -> str:
        return "ruff"

    def analyze(self, workspace: Path, reports_dir: Path) -> RawToolResult:
        reports_dir.mkdir(parents=True, exist_ok=True)
        artifact = reports_dir / "ruff.json"

        if shutil.which("ruff") is None:
            artifact.write_text("[]", encoding="utf-8")
            return RawToolResult("ruff", 127, "", "ruff not installed", artifact.name)

        # Ruff writes JSON to stdout; we persist it as an artifact
        r = run_cmd(
            ["ruff", "check", ".", "--output-format", "json"],
            cwd=workspace,
            timeout_sec=180,
        )

        artifact.write_text(r.stdout or "[]", encoding="utf-8")

        return RawToolResult(
            tool="ruff",
            exit_code=r.exit_code,
            stdout=r.stdout,
            stderr=r.stderr,
            artifact=artifact.name,
        )
