"""Prompt templates for LLM-based test generation.

Each oracle type (crash, property, metamorphic) has its own user prompt
template. The system prompt is shared across all oracle types.

These prompts are the starting point for T-014 (one-shot baseline).
T-021 (prompt engineering iteration) will refine them based on empirical
results across Claude and GPT-4.
"""

from __future__ import annotations

from qallm.verification.models import FunctionInfo

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
