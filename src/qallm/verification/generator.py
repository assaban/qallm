"""LLM-based test generator (T-014).

Generates pytest test cases for Python functions by calling an LLM
with a structured prompt. The generator supports multiple oracle types
(crash, property, metamorphic), starting with crash oracle.

Usage:
    generator = TestGenerator(llm_registry)
    result = generator.generate(function_info, oracle="crash")
    # result.test_code contains valid pytest code (or result.is_valid is False)
"""

from __future__ import annotations

import logging
import re

from qallm.llm.base import LLMModel, TokenTracker
from qallm.verification.models import FunctionInfo, GeneratedTest, OracleType
from qallm.verification.prompts import (
    SYSTEM_PROMPT,
    build_crash_oracle_prompt,
)

logger = logging.getLogger(__name__)

PROMPT_BUILDERS = {
    "crash": build_crash_oracle_prompt,
}


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening fence (```python or ```)
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _validate_test_code(code: str) -> tuple[bool, str | None]:
    """Check if the generated code compiles and contains test functions."""
    if not code.strip():
        return False, "Empty test code"

    try:
        compile(code, "<generated_test>", "exec")
    except SyntaxError as exc:
        return False, f"Syntax error: {exc}"

    # Check that at least one test function exists
    if not re.search(r"^def test_", code, re.MULTILINE):
        return False, "No test functions found (expected functions starting with 'test_')"

    return True, None


def _fix_source_import(test_code: str, module_name: str) -> str:
    """Replace 'source_module' placeholder with the actual module name.

    The prompt instructs the LLM to import from 'source_module'. At runtime,
    we replace this with the actual module name so the test can find the
    function under test.
    """
    return test_code.replace("source_module", module_name)


class TestGenerator:
    """Generates pytest test cases for Python functions via LLM."""

    __test__ = False  # prevent pytest from collecting this as a test class

    def __init__(self, llm: LLMModel, tracker: TokenTracker | None = None) -> None:
        self.llm = llm
        self.tracker = tracker or TokenTracker(budget=50_000)

    def generate(
        self,
        func: FunctionInfo,
        oracle: OracleType = "crash",
        module_name: str = "source_module",
    ) -> GeneratedTest:
        """Generate test cases for a single function.

        Args:
            func: The function to generate tests for.
            oracle: Which oracle type to use for prompting.
            module_name: The module name the test file should import from.

        Returns:
            GeneratedTest with the generated code and metadata.
        """
        builder = PROMPT_BUILDERS.get(oracle)
        if builder is None:
            return GeneratedTest(
                function_name=func.name,
                oracle=oracle,
                test_code="",
                is_valid=False,
                generation_error=f"Unknown oracle type: {oracle}",
            )

        user_prompt = builder(func)

        logger.info(
            "Generating %s tests for %s via %s",
            oracle,
            func.name,
            self.llm.name(),
        )

        resp = self.llm.chat(SYSTEM_PROMPT, user_prompt, self.tracker)

        if resp.error:
            logger.warning("LLM error generating tests for %s: %s", func.name, resp.error)
            return GeneratedTest(
                function_name=func.name,
                oracle=oracle,
                test_code="",
                is_valid=False,
                generation_error=resp.error,
                model=resp.model,
                provider=resp.provider,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
            )

        raw_code = _strip_markdown_fences(resp.content)
        test_code = _fix_source_import(raw_code, module_name)
        is_valid, validation_error = _validate_test_code(test_code)

        if not is_valid:
            logger.warning(
                "Generated tests for %s are invalid: %s",
                func.name,
                validation_error,
            )

        return GeneratedTest(
            function_name=func.name,
            oracle=oracle,
            test_code=test_code,
            is_valid=is_valid,
            generation_error=validation_error,
            model=resp.model,
            provider=resp.provider,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )
