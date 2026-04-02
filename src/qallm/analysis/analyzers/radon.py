from __future__ import annotations

import shutil
from pathlib import Path

from qallm.analysis.util import run_cmd

from .base import RawToolResult, StaticCodeAnalyzer


class RadonAnalyzer(StaticCodeAnalyzer):
    def tool_name(self) -> str:
        return "radon"

    def analyze(self, workspace: Path, reports_dir: Path) -> RawToolResult:
        reports_dir.mkdir(parents=True, exist_ok=True)
        artifact = reports_dir / "radon_cc.json"

        if shutil.which("radon") is None:
            artifact.write_text("{}", encoding="utf-8")
            return RawToolResult("radon", 127, "", "radon not installed", artifact.name)

        # radon outputs JSON to stdout for cc -j
        r = run_cmd(["radon", "cc", ".", "-j"], cwd=workspace, timeout_sec=240)
        artifact.write_text(r.stdout or "{}", encoding="utf-8")

        return RawToolResult("radon", r.exit_code, r.stdout, r.stderr, artifact.name)
