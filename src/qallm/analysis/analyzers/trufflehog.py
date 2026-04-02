from __future__ import annotations

import shutil
from pathlib import Path

from qallm.analysis.util import run_cmd

from .base import RawToolResult, StaticCodeAnalyzer


class TruffleHogAnalyzer(StaticCodeAnalyzer):
    def tool_name(self) -> str:
        return "trufflehog"

    def analyze(self, workspace: Path, reports_dir: Path) -> RawToolResult:
        reports_dir.mkdir(parents=True, exist_ok=True)
        artifact = reports_dir / "trufflehog.jsonl"

        if shutil.which("trufflehog") is None:
            artifact.write_text("", encoding="utf-8")
            return RawToolResult(
                tool="trufflehog",
                exit_code=127,
                stdout="",
                stderr="trufflehog not installed",
                artifact=artifact.name,
            )

        # TruffleHog prints one JSON object per line to stdout with --json
        # We scan filesystem at workspace path (.)
        r = run_cmd(
            [
                "trufflehog",
                "filesystem",
                ".",
                "--json",
                "--no-update",  # stable for CI
            ],
            cwd=workspace,
            timeout_sec=300,
        )

        artifact.write_text(r.stdout or "", encoding="utf-8")

        return RawToolResult(
            tool="trufflehog",
            exit_code=r.exit_code,
            stdout=r.stdout,
            stderr=r.stderr,
            artifact=artifact.name,
        )
