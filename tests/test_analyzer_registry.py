"""Tests for AnalyzerRegistry."""

from pathlib import Path

import pytest

from qallm.analysis.analyzers.bandit import BanditAnalyzer
from qallm.analysis.analyzers.radon import RadonAnalyzer
from qallm.analysis.analyzers.registry import AnalyzerRegistry
from qallm.analysis.analyzers.ruff import RuffAnalyzer
from qallm.analysis.analyzers.trufflehog import TruffleHogAnalyzer


def _registry() -> AnalyzerRegistry:
    return AnalyzerRegistry(
        [
            BanditAnalyzer(),
            RuffAnalyzer(),
            RadonAnalyzer(),
            TruffleHogAnalyzer(),
        ]
    )


def test_registry_list_returns_all_tool_names():
    reg = _registry()
    names = reg.list()
    assert set(names) == {"bandit", "ruff", "radon", "trufflehog"}
    assert names == sorted(names)


def test_registry_pick_with_no_selection_returns_all(tmp_path: Path, monkeypatch):
    reg = _registry()
    picked = reg.pick(None)
    assert len(picked) == 4
    assert {a.tool_name() for a in picked} == {"bandit", "ruff", "radon", "trufflehog"}


def test_registry_pick_with_selection_filters(tmp_path: Path):
    reg = _registry()
    picked = reg.pick(["bandit", "ruff"])
    assert len(picked) == 2
    assert {a.tool_name() for a in picked} == {"bandit", "ruff"}


def test_registry_pick_ignores_unknown_names():
    reg = _registry()
    picked = reg.pick(["bandit", "unknown_tool"])
    assert len(picked) == 1
    assert picked[0].tool_name() == "bandit"


def test_registry_get_known_tool():
    reg = _registry()
    assert isinstance(reg.get("ruff"), RuffAnalyzer)


def test_registry_get_unknown_tool_raises():
    reg = _registry()
    with pytest.raises(KeyError):
        reg.get("nonexistent")
