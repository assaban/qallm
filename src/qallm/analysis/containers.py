from __future__ import annotations


def build_analyzer_registry():
    from qallm.analysis.analyzers.bandit import BanditAnalyzer
    from qallm.analysis.analyzers.radon import RadonAnalyzer
    from qallm.analysis.analyzers.registry import AnalyzerRegistry
    from qallm.analysis.analyzers.ruff import RuffAnalyzer
    from qallm.analysis.analyzers.trufflehog import TruffleHogAnalyzer

    return AnalyzerRegistry([BanditAnalyzer(), RuffAnalyzer(), RadonAnalyzer(), TruffleHogAnalyzer()])


def build_normalizer_registry():
    from qallm.analysis.normalizers.bandit_normalizer import BanditNormalizer
    from qallm.analysis.normalizers.radon_normalizer import RadonNormalizer
    from qallm.analysis.normalizers.registry import NormalizerRegistry
    from qallm.analysis.normalizers.ruff_normalizer import RuffNormalizer
    from qallm.analysis.normalizers.trufflehog_normalizer import TruffleHogNormalizer

    return NormalizerRegistry(
        [
            BanditNormalizer(),
            RuffNormalizer(),
            RadonNormalizer(),
            TruffleHogNormalizer(),
        ]
    )
