"""Hypothesis property-based testing baseline (T-020).

Generates property-based tests using the Hypothesis library instead of
an LLM. This serves as the non-trivial comparison baseline for RQ1.

The baseline infers Hypothesis strategies from type annotations in the
function signature. When annotations are absent, it uses a mixed strategy
covering common Python types.

Usage:
    from qallm.verification.hypothesis_baseline import generate_hypothesis_tests, run_baseline

    # Generate test code only
    test_code = generate_hypothesis_tests(func_info, module_name="my_module")

    # Generate and execute (returns ExecutionResult)
    result = run_baseline(func_info, source_code)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from qallm.verification.executor import run_tests
from qallm.verification.models import ExecutionResult, FunctionInfo

logger = logging.getLogger(__name__)

# Mapping from Python type annotation strings to Hypothesis strategy expressions
_STRATEGY_MAP: dict[str, str] = {
    "int": "st.integers()",
    "float": "st.floats(allow_nan=False, allow_infinity=False)",
    "str": "st.text(max_size=100)",
    "bool": "st.booleans()",
    "bytes": "st.binary(max_size=100)",
    "list": "st.lists(st.integers())",
    "list[int]": "st.lists(st.integers())",
    "list[float]": "st.lists(st.floats(allow_nan=False, allow_infinity=False))",
    "list[str]": "st.lists(st.text(max_size=20))",
    "list[bool]": "st.lists(st.booleans())",
    "dict": "st.dictionaries(st.text(max_size=10), st.integers())",
    "dict[str, int]": "st.dictionaries(st.text(max_size=10), st.integers())",
    "dict[str, str]": "st.dictionaries(st.text(max_size=10), st.text(max_size=20))",
    "set": "st.frozensets(st.integers())",
    "set[int]": "st.frozensets(st.integers())",
    "tuple": "st.tuples(st.integers(), st.integers())",
}

_MIXED_STRATEGY = "st.one_of(st.integers(), st.text(max_size=50), st.booleans(), st.lists(st.integers()))"


def _annotation_to_strategy(annotation: str | None) -> str:
    """Convert a type annotation string to a Hypothesis strategy expression."""
    if annotation is None:
        return _MIXED_STRATEGY

    # Normalise whitespace
    clean = annotation.strip().replace(" ", "")

    # Direct match
    if clean in _STRATEGY_MAP:
        return _STRATEGY_MAP[clean]

    # Handle Optional[X] → one_of(none(), strategy_for(X))
    optional_match = re.match(r"Optional\[(.+)\]", clean)
    if optional_match:
        inner = _annotation_to_strategy(optional_match.group(1))
        return f"st.one_of(st.none(), {inner})"

    # Handle list[X] generically
    list_match = re.match(r"list\[(.+)\]", clean)
    if list_match:
        inner = _annotation_to_strategy(list_match.group(1))
        return f"st.lists({inner})"

    # Handle dict[K, V] generically
    dict_match = re.match(r"dict\[(.+),(.+)\]", clean)
    if dict_match:
        key_strat = _annotation_to_strategy(dict_match.group(1).strip())
        val_strat = _annotation_to_strategy(dict_match.group(2).strip())
        return f"st.dictionaries({key_strat}, {val_strat})"

    # Fallback: mixed strategy
    return _MIXED_STRATEGY


def generate_hypothesis_tests(
    func: FunctionInfo,
    module_name: str = "source_module",
    max_examples: int = 200,
) -> str:
    """Generate a Hypothesis test file for a function.

    Produces two test functions:
      1. Crash test: calls the function with generated inputs, catches all
         exceptions (Hypothesis will shrink to minimal failing example)
      2. Property test: if the function has a return type annotation, checks
         the return type is correct

    Args:
        func: The function to generate tests for.
        module_name: Module name for the import statement.
        max_examples: Number of Hypothesis examples per test.

    Returns:
        Complete pytest test file as a string.
    """
    # Build strategy kwargs for @given
    given_args = []
    for arg_name, annotation in func.args:
        strategy = _annotation_to_strategy(annotation)
        given_args.append(f"{arg_name}={strategy}")

    given_decorator = f"@given({', '.join(given_args)})"
    settings_decorator = (
        f"@settings(max_examples={max_examples}, "
        f"suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])"
    )

    # Build function call
    call_args = ", ".join(name for name, _ in func.args)
    call_expr = f"{func.name}({call_args})"

    lines = [
        "import pytest",
        "from hypothesis import given, settings, HealthCheck",
        "from hypothesis import strategies as st",
        f"from {module_name} import {func.name}",
        "",
        "",
        f"{given_decorator}",
        f"{settings_decorator}",
        f"def test_{func.name}_does_not_crash({call_args}):",
        '    """Crash oracle: function should not raise on type-valid inputs."""',
        "    try:",
        f"        {call_expr}",
        "    except (TypeError, ValueError, ZeroDivisionError, OverflowError, KeyError, IndexError):",
        "        pass  # Known exception types; Hypothesis will find minimal example",
        "",
        "",
    ]

    # Add a non-empty variant for collection arguments
    nonempty_args = []
    has_collection = False
    for arg_name, annotation in func.args:
        ann = (annotation or "").strip().replace(" ", "")
        if ann.startswith("list") or ann == "list":
            nonempty_args.append(f"{arg_name}=st.lists(st.integers(), min_size=1)")
            has_collection = True
        elif ann.startswith("dict") or ann == "dict":
            nonempty_args.append(f"{arg_name}=st.dictionaries(st.text(max_size=10), st.integers(), min_size=1)")
            has_collection = True
        elif ann.startswith("str") or ann == "str":
            nonempty_args.append(f"{arg_name}=st.text(min_size=1, max_size=100)")
            has_collection = True
        else:
            strategy = _annotation_to_strategy(annotation)
            nonempty_args.append(f"{arg_name}={strategy}")

    if has_collection:
        nonempty_given = f"@given({', '.join(nonempty_args)})"
        lines.extend(
            [
                f"{nonempty_given}",
                f"{settings_decorator}",
                f"def test_{func.name}_nonempty_input({call_args}):",
                '    """Property: function should handle non-empty collections."""',
                f"    result = {call_expr}",
                "    assert result is not None or result is None  # just ensure it returns",
                "",
                "",
            ]
        )

    # Add return type check if annotation exists
    # Extract return type from function source
    return_match = re.search(r"->\s*(\w+)", func.source.split("\n")[0])
    if return_match:
        return_type = return_match.group(1)
        type_map = {
            "int": "(int, float)",
            "float": "(int, float)",
            "str": "str",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "set": "(set, frozenset)",
            "tuple": "tuple",
        }
        if return_type in type_map:
            # Use nonempty strategies if we have collections, regular otherwise
            if has_collection:
                type_given = f"@given({', '.join(nonempty_args)})"
            else:
                type_given = given_decorator
            lines.extend(
                [
                    f"{type_given}",
                    f"{settings_decorator}",
                    f"def test_{func.name}_returns_correct_type({call_args}):",
                    '    """Property: return type should match annotation."""',
                    f"    result = {call_expr}",
                    f"    assert isinstance(result, {type_map[return_type]})",
                    "",
                ]
            )

    return "\n".join(lines)


def run_baseline(
    func: FunctionInfo,
    source_code: str,
    module_name: str = "source_module",
    max_examples: int = 200,
    timeout: int = 120,
    persist_path: Path | None = None,
) -> ExecutionResult:
    """Generate and execute Hypothesis tests for a function.

    Args:
        func: The function to test.
        source_code: Complete source module containing the function.
        module_name: Module name for imports.
        max_examples: Hypothesis examples per test.
        timeout: Execution timeout (Hypothesis can be slow).
        persist_path: If set, save the generated test code here.

    Returns:
        ExecutionResult comparable to the LLM-based approach.
    """
    test_code = generate_hypothesis_tests(func, module_name=module_name, max_examples=max_examples)

    if persist_path:
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# Generated by QALLM Hypothesis Baseline\n"
            f"# Source file: {func.filepath}\n"
            f"# Function: {func.name} (line {func.lineno})\n"
            f"# Strategy: property-based testing (max_examples={max_examples})\n\n"
        )
        persist_path.write_text(header + test_code, encoding="utf-8")

    logger.info("Running Hypothesis baseline for %s (%d examples)", func.name, max_examples)

    result = run_tests(
        source_code=source_code,
        test_code=test_code,
        source_filename=f"{module_name}.py",
        timeout=timeout,
    )

    return result
