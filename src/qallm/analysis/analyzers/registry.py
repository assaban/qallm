from __future__ import annotations

from typing import Iterable

from .base import StaticCodeAnalyzer


class AnalyzerRegistry:
    def __init__(self, analyzers: Iterable[StaticCodeAnalyzer]):
        self._by_name = {a.tool_name(): a for a in analyzers}

    def list(self) -> list[str]:
        return sorted(self._by_name.keys())

    def get(self, name: str) -> StaticCodeAnalyzer:
        return self._by_name[name]

    def pick(self, selected: list[str] | None) -> list[StaticCodeAnalyzer]:
        if not selected:
            return [self._by_name[k] for k in self.list()]
        return [self._by_name[n] for n in selected if n in self._by_name]
