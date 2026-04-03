"""Tests for NormalizerRegistry."""

from qallm.analysis.normalizers.bandit_normalizer import BanditNormalizer
from qallm.analysis.normalizers.radon_normalizer import RadonNormalizer
from qallm.analysis.normalizers.registry import NormalizerRegistry
from qallm.analysis.normalizers.ruff_normalizer import RuffNormalizer
from qallm.analysis.normalizers.trufflehog_normalizer import TruffleHogNormalizer


def _registry() -> NormalizerRegistry:
    return NormalizerRegistry(
        [
            BanditNormalizer(),
            RuffNormalizer(),
            RadonNormalizer(),
            TruffleHogNormalizer(),
        ]
    )


def test_registry_get_known_tools():
    reg = _registry()
    assert isinstance(reg.get("bandit"), BanditNormalizer)
    assert isinstance(reg.get("ruff"), RuffNormalizer)
    assert isinstance(reg.get("radon"), RadonNormalizer)
    assert isinstance(reg.get("trufflehog"), TruffleHogNormalizer)


def test_registry_get_unknown_tool_returns_none():
    reg = _registry()
    assert reg.get("nonexistent") is None


def test_registry_list_returns_sorted_names():
    reg = _registry()
    names = reg.list()
    assert names == sorted(names)
    assert set(names) == {"bandit", "ruff", "radon", "trufflehog"}
