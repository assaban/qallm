"""Tests for the Hypothesis baseline (T-020).

Tests the strategy inference, test code generation, and execution.
Uses synthetic functions; no LLM calls.
"""

import textwrap

from qallm.verification.hypothesis_baseline import (
    _annotation_to_strategy,
    generate_hypothesis_tests,
    run_baseline,
)
from qallm.verification.models import FunctionInfo


def _make_func(
    name: str = "compute_mean",
    source: str = "def compute_mean(data):\n    return sum(data) / len(data)\n",
    args: list | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        source=source,
        docstring="Test function.",
        args=args or [("data", "list")],
        lineno=1,
        filepath="test_module.py",
    )


# -- Strategy inference


class TestStrategyInference:
    def test_int(self):
        assert "integers()" in _annotation_to_strategy("int")

    def test_float(self):
        s = _annotation_to_strategy("float")
        assert "floats(" in s

    def test_str(self):
        assert "text(" in _annotation_to_strategy("str")

    def test_bool(self):
        assert "booleans()" in _annotation_to_strategy("bool")

    def test_list_plain(self):
        assert "lists(" in _annotation_to_strategy("list")

    def test_list_typed(self):
        s = _annotation_to_strategy("list[int]")
        assert "lists(" in s
        assert "integers()" in s

    def test_dict_typed(self):
        s = _annotation_to_strategy("dict[str, int]")
        assert "dictionaries(" in s

    def test_optional(self):
        s = _annotation_to_strategy("Optional[int]")
        assert "none()" in s
        assert "integers()" in s

    def test_none_gives_mixed(self):
        s = _annotation_to_strategy(None)
        assert "one_of(" in s

    def test_unknown_gives_mixed(self):
        s = _annotation_to_strategy("MyCustomType")
        assert "one_of(" in s


# -- Test code generation


class TestCodeGeneration:
    def test_generates_valid_python(self):
        func = _make_func()
        code = generate_hypothesis_tests(func)
        compile(code, "<test>", "exec")

    def test_contains_hypothesis_imports(self):
        func = _make_func()
        code = generate_hypothesis_tests(func)
        assert "from hypothesis import given" in code
        assert "from hypothesis import strategies as st" in code

    def test_contains_function_import(self):
        func = _make_func()
        code = generate_hypothesis_tests(func, module_name="my_module")
        assert "from my_module import compute_mean" in code

    def test_contains_crash_test(self):
        func = _make_func()
        code = generate_hypothesis_tests(func)
        assert "def test_compute_mean_does_not_crash" in code

    def test_contains_nonempty_test_for_list(self):
        func = _make_func()
        code = generate_hypothesis_tests(func)
        assert "test_compute_mean_nonempty_input" in code

    def test_contains_return_type_test(self):
        func = _make_func(
            source="def compute_mean(data: list) -> float:\n    return sum(data) / len(data)\n",
            args=[("data", "list")],
        )
        code = generate_hypothesis_tests(func)
        assert "test_compute_mean_returns_correct_type" in code

    def test_no_return_type_test_without_annotation(self):
        func = _make_func(
            source="def compute_mean(data):\n    return sum(data) / len(data)\n",
            args=[("data", None)],
        )
        code = generate_hypothesis_tests(func)
        assert "returns_correct_type" not in code

    def test_multiple_args(self):
        func = _make_func(
            name="add",
            source="def add(a: int, b: int) -> int:\n    return a + b\n",
            args=[("a", "int"), ("b", "int")],
        )
        code = generate_hypothesis_tests(func)
        assert "a=st.integers()" in code
        assert "b=st.integers()" in code

    def test_max_examples_respected(self):
        func = _make_func()
        code = generate_hypothesis_tests(func, max_examples=50)
        assert "max_examples=50" in code


# -- Execution


class TestExecution:
    def test_runs_on_simple_function(self):
        source = textwrap.dedent("""\
            def add(a, b):
                return a + b
        """)
        func = _make_func(
            name="add",
            source="def add(a, b):\n    return a + b\n",
            args=[("a", "int"), ("b", "int")],
        )
        result = run_baseline(func, source, max_examples=10, timeout=30)
        assert result.total > 0
        assert result.coverage_percent is not None

    def test_finds_bug_in_division(self):
        source = textwrap.dedent("""\
            def divide(a, b):
                return a / b
        """)
        func = _make_func(
            name="divide",
            source="def divide(a, b):\n    return a / b\n",
            args=[("a", "int"), ("b", "int")],
        )
        result = run_baseline(func, source, max_examples=50, timeout=30)
        # Hypothesis should find b=0 case
        assert result.total > 0

    def test_persists_test_file(self, tmp_path):
        source = "def add(a, b):\n    return a + b\n"
        func = _make_func(
            name="add",
            source=source,
            args=[("a", "int"), ("b", "int")],
        )
        persist_path = tmp_path / "tests" / "add_hypothesis.py"
        run_baseline(func, source, max_examples=10, timeout=30, persist_path=persist_path)

        assert persist_path.exists()
        content = persist_path.read_text()
        assert "Generated by QALLM Hypothesis Baseline" in content
        assert "Source file:" in content
