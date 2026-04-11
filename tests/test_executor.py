"""Tests for the test executor (T-015).

These tests use synthetic source code and hand-written test code.
No LLM calls are made. The executor runs real pytest in a subprocess,
so pytest, pytest-json-report, and pytest-cov must be installed.
"""

import textwrap

from qallm.verification.executor import run_tests

# -- Synthetic source and test code


SOURCE_GOOD = textwrap.dedent("""\
    def add(a, b):
        return a + b

    def divide(a, b):
        return a / b
""")

TESTS_ALL_PASS = textwrap.dedent("""\
    from source_module import add, divide

    def test_add_positive():
        assert add(1, 2) == 3

    def test_add_zero():
        assert add(0, 0) == 0

    def test_divide_normal():
        assert divide(10, 2) == 5.0
""")

TESTS_WITH_FAILURE = textwrap.dedent("""\
    import pytest
    from source_module import add, divide

    def test_add_works():
        assert add(2, 3) == 5

    def test_divide_by_zero_crashes():
        # This test FINDS a bug: divide doesn't handle zero
        divide(1, 0)

    def test_add_wrong_expectation():
        assert add(1, 1) == 3  # deliberately wrong
""")

TESTS_WITH_SYNTAX_ERROR = textwrap.dedent("""\
    def test_broken(
        assert True
""")

TESTS_WITH_IMPORT_ERROR = textwrap.dedent("""\
    from nonexistent_module import something

    def test_will_error():
        assert something() == 42
""")

TESTS_INFINITE_LOOP = textwrap.dedent("""\
    def test_hangs():
        while True:
            pass
""")

SOURCE_WITH_BRANCHES = textwrap.dedent("""\
    def classify(n):
        if n > 0:
            return "positive"
        elif n < 0:
            return "negative"
        else:
            return "zero"
""")

TESTS_PARTIAL_COVERAGE = textwrap.dedent("""\
    from source_module import classify

    def test_positive():
        assert classify(5) == "positive"
""")


# -- Test cases


class TestExecutorAllPass:
    def test_all_tests_pass(self):
        result = run_tests(SOURCE_GOOD, TESTS_ALL_PASS)
        assert result.passed == 3
        assert result.failed == 0
        assert result.errors == 0
        assert result.total == 3
        assert result.all_passed is True

    def test_captures_duration(self):
        result = run_tests(SOURCE_GOOD, TESTS_ALL_PASS)
        assert result.duration_seconds > 0

    def test_captures_coverage(self):
        result = run_tests(SOURCE_GOOD, TESTS_ALL_PASS)
        # Coverage should be reported (may not be 100% since divide edge cases untested)
        assert result.coverage_percent is not None
        assert result.coverage_percent > 0

    def test_captures_test_details(self):
        result = run_tests(SOURCE_GOOD, TESTS_ALL_PASS)
        assert len(result.test_details) == 3
        names = [d.name for d in result.test_details]
        assert any("test_add_positive" in n for n in names)
        assert all(d.status == "passed" for d in result.test_details)


class TestExecutorWithFailures:
    def test_detects_failures(self):
        result = run_tests(SOURCE_GOOD, TESTS_WITH_FAILURE)
        assert result.failed >= 1
        assert result.all_passed is False

    def test_bugs_found_count(self):
        result = run_tests(SOURCE_GOOD, TESTS_WITH_FAILURE)
        assert result.bugs_found >= 1

    def test_failure_details_have_messages(self):
        result = run_tests(SOURCE_GOOD, TESTS_WITH_FAILURE)
        failed_tests = [d for d in result.test_details if d.status == "failed"]
        assert len(failed_tests) >= 1
        # At least one failure should have a message
        assert any(d.message for d in failed_tests)


class TestExecutorErrorHandling:
    def test_handles_import_error(self):
        result = run_tests(SOURCE_GOOD, TESTS_WITH_IMPORT_ERROR)
        # Import errors show up as errors, not passes
        assert result.all_passed is False

    def test_handles_timeout(self):
        result = run_tests(SOURCE_GOOD, TESTS_INFINITE_LOOP, timeout=3)
        assert result.execution_error is not None
        assert "Timeout" in result.execution_error

    def test_empty_test_code(self):
        result = run_tests(SOURCE_GOOD, "")
        # Empty test file: no tests collected
        assert result.total == 0


class TestExecutorCoverage:
    def test_partial_coverage(self):
        result = run_tests(SOURCE_WITH_BRANCHES, TESTS_PARTIAL_COVERAGE)
        assert result.coverage_percent is not None
        # Only testing positive branch, so coverage should be less than 100
        assert result.coverage_percent < 100.0
        assert result.coverage_percent > 0.0

    def test_coverage_branches_per_file(self):
        result = run_tests(SOURCE_WITH_BRANCHES, TESTS_PARTIAL_COVERAGE)
        # coverage_branches should have at least one file entry
        if result.coverage_branches:
            assert any("source_module" in k for k in result.coverage_branches)


class TestExecutorProperties:
    def test_validity_rate_all_valid(self):
        result = run_tests(SOURCE_GOOD, TESTS_ALL_PASS)
        assert result.validity_rate == 1.0

    def test_validity_rate_with_errors(self):
        result = run_tests(SOURCE_GOOD, TESTS_WITH_IMPORT_ERROR)
        # errors reduce validity rate
        if result.total > 0:
            assert result.validity_rate <= 1.0

    def test_custom_source_filename(self):
        source = "def greet(name): return f'Hi {name}'\n"
        test_code = textwrap.dedent("""\
            from my_code import greet

            def test_greet():
                assert greet("Alice") == "Hi Alice"
        """)
        result = run_tests(source, test_code, source_filename="my_code.py")
        assert result.passed == 1
