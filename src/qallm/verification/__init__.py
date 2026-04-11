"""RL-guided test generation and verification module.

This is the core thesis contribution: the Test Case Agent from the
Agentic Workflow proposed by Islam & Zhao.

Key classes:
    TestGenerator: LLM-based test code generation
    TestGenerationLoop: Iterative RL feedback loop
    ExecutionResult: Test execution outcome
    TestGenerationSession: Complete record of an RL run
"""

from qallm.verification.executor import run_tests
from qallm.verification.extractor import extract_functions_from_source
from qallm.verification.generator import TestGenerator
from qallm.verification.loop import TestGenerationLoop, save_session
from qallm.verification.models import (
    ExecutionResult,
    FunctionInfo,
    GeneratedTest,
    RewardBreakdown,
    RoundResult,
    TestGenerationSession,
)
from qallm.verification.reward import RewardWeights, compute_reward

__all__ = [
    "TestGenerator",
    "TestGenerationLoop",
    "run_tests",
    "extract_functions_from_source",
    "save_session",
    "compute_reward",
    "RewardWeights",
    "FunctionInfo",
    "GeneratedTest",
    "ExecutionResult",
    "RewardBreakdown",
    "RoundResult",
    "TestGenerationSession",
]
