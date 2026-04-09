"""Tests for the LLM-based test generator (T-014).

All tests use a mock LLM to avoid API calls and costs.
"""

import textwrap

from qallm.llm.base import LLMModel, LLMResponse, TokenTracker
from qallm.verification.generator import (
    TestGenerator,
    _fix_source_import,
    _strip_markdown_fences,
    _validate_test_code,
)
from qallm.verification.models import FunctionInfo

# -- Helpers


def _make_func(name: str = "compute_mean", source: str | None = None) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        source=source or "def compute_mean(data):\n    return sum(data) / len(data)\n",
        docstring="Compute the arithmetic mean.",
        args=[("data", "list")],
        lineno=1,
        filepath="source_module.py",
    )


VALID_TEST_CODE = textwrap.dedent("""\
    import pytest
    from source_module import compute_mean

    def test_normal():
        assert compute_mean([1, 2, 3]) == 2.0

    def test_single():
        assert compute_mean([5]) == 5.0

    def test_empty():
        with pytest.raises(ZeroDivisionError):
            compute_mean([])

    def test_negative():
        assert compute_mean([-1, 1]) == 0.0
""")


class FakeLLM(LLMModel):
    """Mock LLM that returns predetermined content."""

    def __init__(self, content: str = "", error: str | None = None):
        self._content = content
        self._error = error

    def name(self) -> str:
        return "fake-model"

    def is_configured(self) -> bool:
        return True

    def chat(self, system: str, user: str, tracker: TokenTracker | None = None) -> LLMResponse:
        resp = LLMResponse(
            content=self._content,
            input_tokens=100,
            output_tokens=200,
            model="fake-model",
            provider="fake",
            error=self._error,
        )
        if tracker:
            tracker.record(resp)
        return resp


# -- _strip_markdown_fences


def test_strip_fences_removes_python_block():
    raw = "```python\nimport pytest\ndef test_x(): pass\n```"
    assert _strip_markdown_fences(raw) == "import pytest\ndef test_x(): pass"


def test_strip_fences_removes_plain_block():
    raw = "```\ncode here\n```"
    assert _strip_markdown_fences(raw) == "code here"


def test_strip_fences_noop_when_no_fences():
    raw = "import pytest\ndef test_x(): pass"
    assert _strip_markdown_fences(raw) == raw


def test_strip_fences_handles_empty():
    assert _strip_markdown_fences("") == ""


# -- _validate_test_code


def test_validate_accepts_valid_code():
    is_valid, error = _validate_test_code(VALID_TEST_CODE)
    assert is_valid is True
    assert error is None


def test_validate_rejects_empty():
    is_valid, error = _validate_test_code("")
    assert is_valid is False
    assert "Empty" in error


def test_validate_rejects_syntax_error():
    is_valid, error = _validate_test_code("def test_x(:\n    pass\n")
    assert is_valid is False
    assert "Syntax error" in error


def test_validate_rejects_no_test_functions():
    is_valid, error = _validate_test_code("import pytest\nx = 1\n")
    assert is_valid is False
    assert "No test functions" in error


# -- _fix_source_import


def test_fix_import_replaces_placeholder():
    code = "from source_module import add\n"
    fixed = _fix_source_import(code, "my_module")
    assert fixed == "from my_module import add\n"


def test_fix_import_replaces_all_occurrences():
    code = "from source_module import add\nfrom source_module import sub\n"
    fixed = _fix_source_import(code, "calc")
    assert "from calc import add" in fixed
    assert "from calc import sub" in fixed


# -- TestGenerator.generate


def test_generate_returns_valid_test():
    llm = FakeLLM(content=VALID_TEST_CODE)
    gen = TestGenerator(llm)
    result = gen.generate(_make_func(), oracle="crash")

    assert result.is_valid is True
    assert result.generation_error is None
    assert result.function_name == "compute_mean"
    assert result.oracle == "crash"
    assert "def test_normal" in result.test_code
    assert result.model == "fake-model"
    assert result.input_tokens == 100
    assert result.output_tokens == 200


def test_generate_handles_markdown_fences():
    wrapped = f"```python\n{VALID_TEST_CODE}\n```"
    llm = FakeLLM(content=wrapped)
    gen = TestGenerator(llm)
    result = gen.generate(_make_func())

    assert result.is_valid is True


def test_generate_handles_llm_error():
    llm = FakeLLM(error="API rate limit exceeded")
    gen = TestGenerator(llm)
    result = gen.generate(_make_func())

    assert result.is_valid is False
    assert "rate limit" in result.generation_error


def test_generate_handles_invalid_output():
    llm = FakeLLM(content="This is not Python code at all.")
    gen = TestGenerator(llm)
    result = gen.generate(_make_func())

    assert result.is_valid is False
    assert result.generation_error is not None


def test_generate_unknown_oracle():
    llm = FakeLLM(content=VALID_TEST_CODE)
    gen = TestGenerator(llm)
    result = gen.generate(_make_func(), oracle="nonexistent")

    assert result.is_valid is False
    assert "Unknown oracle" in result.generation_error


def test_generate_tracks_tokens():
    llm = FakeLLM(content=VALID_TEST_CODE)
    tracker = TokenTracker(budget=50_000)
    gen = TestGenerator(llm, tracker=tracker)
    gen.generate(_make_func())

    assert tracker.calls == 1
    assert tracker.total_input == 100
    assert tracker.total_output == 200


def test_generate_replaces_module_name():
    code = "from source_module import compute_mean\ndef test_it(): pass\n"
    llm = FakeLLM(content=code)
    gen = TestGenerator(llm)
    result = gen.generate(_make_func(), module_name="my_analysis")

    assert "from my_analysis import" in result.test_code
