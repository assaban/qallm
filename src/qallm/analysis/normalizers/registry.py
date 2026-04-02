from __future__ import annotations

from typing import Iterable

from .base import ToolNormalizer


class NormalizerRegistry:
    def __init__(self, normalizers: Iterable[ToolNormalizer]):
        self._by_tool = {n.tool_name: n for n in normalizers}

    def list(self) -> list[str]:
        return sorted(self._by_tool.keys())

    def get(self, tool: str) -> ToolNormalizer | None:
        return self._by_tool.get(tool)
