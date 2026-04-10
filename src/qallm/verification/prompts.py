"""Prompt templates for LLM-based test generation.

Each oracle type (crash, property, metamorphic) has its own user prompt
template. The system prompt is shared across all oracle types.

These prompts are the starting point for T-014 (one-shot baseline).
T-021 (prompt engineering iteration) will refine them based on empirical
results across Claude and GPT-4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qallm.verification.models import FunctionInfo

if TYPE_CHECKING:
    from qallm.verification.models import ExecutionResult, RewardBreakdown

SYSTEM_PROMPT = """\
You are a senior Python test engineer. Your task is to generate pytest test \
cases for the given function.

Rules:
1. Output ONLY valid Python code. No markdown fences, no explanations, no \
comments outside the test file.
2. Import pytest at the top.
3. Import the function under test from 'source_module' (this will be \
replaced at runtime with the correct module name).
4. Each test function must start with 'test_'.
5. Generate 4 to 8 test cases covering normal inputs, edge cases, and \
boundary conditions.
6. Every test must contain at least one assert statement or pytest.raises.
7. Do not use external libraries beyond pytest and the standard library.
8. Do not mock the function under test; call it directly.
"""


def build_crash_oracle_prompt(func: FunctionInfo) -> str:
    """Build a user prompt for crash oracle test generation.

    The crash oracle focuses on: does the function handle edge case inputs
    without raising unhandled exceptions? Tests should cover empty inputs,
    None values, type boundaries, and unusual but valid inputs.
    """
    parts = [
        "## Function under test\n",
        f"```python\n{func.source}\n```\n",
    ]

    if func.docstring:
        parts.append(f"## Docstring\n{func.docstring}\n")

    if func.args:
        arg_lines = []
        for name, annotation in func.args:
            if annotation:
                arg_lines.append(f"  {name}: {annotation}")
            else:
                arg_lines.append(f"  {name}: (no type annotation)")
        parts.append("## Arguments\n" + "\n".join(arg_lines) + "\n")

    parts.append(
        "## Task\n"
        "Generate pytest test cases for the function above. Focus on the "
        "crash oracle: test whether the function handles edge cases without "
        "raising unhandled exceptions.\n\n"
        "Cover these scenarios:\n"
        "  1. Normal/happy path inputs\n"
        "  2. Empty inputs (empty list, empty string, zero, etc.)\n"
        "  3. Boundary values (very large numbers, single element collections)\n"
        "  4. Type edge cases (None if the function might receive it)\n\n"
        "For cases where an exception IS expected, use pytest.raises to assert "
        "the correct exception type.\n\n"
        "Return ONLY the complete test file. Start with imports."
    )

    return "\n".join(parts)


def build_property_oracle_prompt(func: FunctionInfo) -> str:
    """Build a user prompt for property oracle test generation.

    The property oracle focuses on: does the output satisfy invariants
    derivable from the docstring and type hints? For example, a normalise
    function should always return values in [0, 1].

    Status: placeholder for T-018.
    """
    raise NotImplementedError("Property oracle prompt is T-018")


def build_metamorphic_oracle_prompt(func: FunctionInfo) -> str:
    """Build a user prompt for metamorphic oracle test generation.

    The metamorphic oracle focuses on: do related inputs produce consistently
    related outputs? For example, sorting the input to a monotonic function
    should yield sorted output.

    Status: placeholder for T-019.
    """
    raise NotImplementedError("Metamorphic oracle prompt is T-019")


def build_feedback_prompt(
    func: FunctionInfo,
    previous_test_code: str,
    execution: "ExecutionResult",
    reward: "RewardBreakdown",
    round_number: int,
) -> str:
    """Build a follow-up prompt incorporating feedback from the previous round.

    This is the core RL mechanism: the reward signal is translated into
    natural language instructions that guide the LLM toward generating
    better tests in the next round.

    Args:
        func: The function under test (same across all rounds).
        previous_test_code: The test code from the previous round.
        execution: Execution results from the previous round.
        reward: Reward breakdown from the previous round.
        round_number: Current round number (1-indexed).

    Returns:
        User prompt string for the next generation round.
    """
    parts = [
        f"## Round {round_number}: Improve the tests\n",
        "## Function under test\n",
        f"```python\n{func.source}\n```\n",
    ]

    # Show previous test code
    parts.append("## Previous test code (your output from the last round)\n")
    parts.append(f"```python\n{previous_test_code}\n```\n")

    # Show execution results
    parts.append("## Execution results from the previous round\n")
    parts.append(f"  Tests run: {execution.total}\n")
    parts.append(f"  Passed: {execution.passed}\n")
    parts.append(f"  Failed (bugs found): {execution.failed}\n")
    parts.append(f"  Errors (invalid tests): {execution.errors}\n")

    if execution.coverage_percent is not None:
        parts.append(f"  Branch coverage: {execution.coverage_percent:.1f}%\n")

    # Show per-test details for failures and errors
    failures = [d for d in execution.test_details if d.status in ("failed", "error")]
    if failures:
        parts.append("\n## Test failures and errors\n")
        for detail in failures:
            parts.append(f"  {detail.name}: {detail.status}\n")
            if detail.message:
                # Truncate long tracebacks
                msg = detail.message[:300]
                parts.append(f"    {msg}\n")

    # Show reward breakdown
    parts.append(f"\n## Reward score: {reward.total:.2f}\n")
    if reward.bugs_found > 0:
        parts.append(f"  +{reward.bug_reward:.1f} from {reward.bugs_found} bug(s) discovered\n")
    if reward.coverage_gain > 0:
        parts.append(f"  +{reward.coverage_reward:.1f} from {reward.coverage_gain:.1f}% coverage gain\n")
    if reward.invalid_tests > 0:
        parts.append(f"  {reward.validity_penalty:.1f} from {reward.invalid_tests} invalid test(s)\n")
    if reward.redundant_tests > 0:
        parts.append(f"  {reward.redundancy_penalty:.1f} from {reward.redundant_tests} redundant test(s)\n")

    # Instruction for improvement
    parts.append("\n## Task\n")
    parts.append("Generate an IMPROVED set of pytest test cases. Specifically:\n")

    if execution.errors > 0:
        parts.append("  * Fix the invalid tests. Make sure all imports are correct and all tests compile.\n")

    if execution.coverage_percent is not None and execution.coverage_percent < 100:
        parts.append(
            f"  * Current coverage is {execution.coverage_percent:.1f}%. "
            "Generate tests that exercise UNTESTED branches and code paths.\n"
        )

    if reward.redundant_tests > 0:
        parts.append(
            f"  * {reward.redundant_tests} tests were redundant (added no coverage, found no bugs). "
            "Replace them with tests that explore different inputs or edge cases.\n"
        )

    if execution.failed == 0:
        parts.append(
            "  * No bugs were found yet. Try more aggressive edge cases: "
            "empty inputs, None values, very large numbers, negative values, "
            "special characters, concurrent modification, type mismatches.\n"
        )

    parts.append("\nDo NOT repeat the same tests. Generate a completely new test file.\n")
    parts.append("Return ONLY the complete test file. Start with imports.\n")

    return "\n".join(parts)
