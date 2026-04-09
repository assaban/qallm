"""Data models for the verification module.

These models represent the inputs, intermediate artifacts, and outputs
of the test generation and execution pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class FunctionInfo:
    """A single extractable function from a Python source file."""

    name: str
    source: str
    docstring: str | None
    args: list[tuple[str, str | None]]  # (arg_name, annotation_or_None)
    lineno: int
    filepath: str


OracleType = Literal["crash", "property", "metamorphic"]


@dataclass
class GeneratedTest:
    """The output of a single test generation call."""

    function_name: str
    oracle: OracleType
    test_code: str
    is_valid: bool  # True if test_code compiles as Python
    generation_error: str | None = None
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TestDetail:
    """Result of a single test case within a test run."""

    name: str
    status: Literal["passed", "failed", "error", "skipped"]
    message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class ExecutionResult:
    """The output of running a generated test file."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    coverage_percent: float | None = None
    coverage_branches: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    test_details: list[TestDetail] = field(default_factory=list)
    execution_error: str | None = None
    stdout: str = ""
    stderr: str = ""

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.failed == 0 and self.errors == 0

    @property
    def validity_rate(self) -> float:
        """Proportion of tests that actually ran (not errored on collection)."""
        if self.total == 0:
            return 0.0
        return (self.total - self.errors) / self.total

    @property
    def bugs_found(self) -> int:
        """Number of tests that revealed a bug (failed, not errored)."""
        return self.failed
