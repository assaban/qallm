from __future__ import annotations

import shutil
from pathlib import Path

from qallm.analysis.util import run_cmd

from .base import RawToolResult, StaticCodeAnalyzer


class BanditAnalyzer(StaticCodeAnalyzer):
    def tool_name(self) -> str:
        return "bandit"

    def analyze(self, workspace: Path, reports_dir: Path) -> RawToolResult:
        reports_dir.mkdir(parents=True, exist_ok=True)

        artifact = reports_dir / "bandit.json"

        # graceful handling if bandit CLI missing
        if shutil.which("bandit") is None:
            artifact.write_text("{}", encoding="utf-8")
            return RawToolResult(
                tool="bandit",
                exit_code=127,
                stdout="",
                stderr="bandit not installed",
                artifact=artifact.name,
            )

        # bandit writes JSON to file; stdout often empty
        # Use resolved path for -o since cwd differs from artifact location
        r = run_cmd(
            ["bandit", "-r", ".", "-f", "json", "-o", str(artifact.resolve())],
            cwd=workspace,
            timeout_sec=180,
        )

        # if bandit failed before writing the file, ensure artifact exists
        if not artifact.exists():
            artifact.write_text("{}", encoding="utf-8")

        return RawToolResult(
            tool="bandit",
            exit_code=r.exit_code,
            stdout=r.stdout,
            stderr=r.stderr,
            artifact=artifact.name,
        )
