import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class CmdResult:
    exit_code: int
    stdout: str
    stderr: str


def run_cmd(cmd: Sequence[str], cwd: Path, timeout_sec: int = 60) -> CmdResult:
    p = subprocess.run(list(cmd), cwd=str(cwd), capture_output=True, text=True, timeout=timeout_sec)
    return CmdResult(p.returncode, p.stdout or "", p.stderr or "")
