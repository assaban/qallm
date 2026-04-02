from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawToolResult:
    tool: str
    exit_code: int
    stdout: str
    stderr: str
    artifact: str | None = None


class StaticCodeAnalyzer(ABC):
    @abstractmethod
    def tool_name(self) -> str: ...

    @abstractmethod
    def analyze(self, workspace: Path, reports_dir: Path) -> RawToolResult: ...
