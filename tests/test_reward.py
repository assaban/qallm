"""Tests for the reward function (T-016).

All tests use synthetic ExecutionResult objects. No LLM or subprocess calls.
"""

from qallm.verification.models import ExecutionResult, TestDetail
from qallm.verification.reward import RewardWeights, compute_reward


def _exec(
    passed: int = 0,
    failed: int = 0,
    errors: int = 0,
    coverage: float | None = None,
    execution_error: str | None = None,
    details: list[TestDetail] | None = None,
) -> ExecutionResult:
    """Helper to build ExecutionResult with minimal boilerplate."""
    return ExecutionResult(
        passed=passed,
        failed=failed,
        errors=errors,
        total=passed + failed + errors,
        coverage_percent=coverage,
        test_details=details or [],
        execution_error=execution_error,
    )


# -- Bug discovery reward


class TestBugReward:
    def test_one_bug_gives_1_point(self):
        result = compute_reward(_exec(passed=3, failed=1, coverage=60.0))
        assert result.bug_reward == 1.0
        assert result.bugs_found == 1

    def test_multiple_bugs_scale_linearly(self):
        result = compute_reward(_exec(passed=2, failed=3, coverage=40.0))
        assert result.bug_reward == 3.0
        assert result.bugs_found == 3

    def test_no_bugs_gives_zero(self):
        result = compute_reward(_exec(passed=4, coverage=80.0))
        assert result.bug_reward == 0.0


# -- Coverage gain reward


class TestCoverageReward:
    def test_first_round_all_coverage_is_new(self):
        result = compute_reward(_exec(passed=3, coverage=60.0), previous_coverage=None)
        assert result.coverage_gain == 60.0
        assert result.coverage_reward == 30.0  # 60 * 0.5

    def test_coverage_gain_from_previous(self):
        result = compute_reward(_exec(passed=3, coverage=80.0), previous_coverage=60.0)
        assert result.coverage_gain == 20.0
        assert result.coverage_reward == 10.0  # 20 * 0.5

    def test_no_coverage_gain(self):
        result = compute_reward(_exec(passed=3, coverage=60.0), previous_coverage=60.0)
        assert result.coverage_gain == 0.0
        assert result.coverage_reward == 0.0

    def test_coverage_decrease_gives_zero_not_negative(self):
        result = compute_reward(_exec(passed=2, coverage=40.0), previous_coverage=60.0)
        assert result.coverage_gain == 0.0
        assert result.coverage_reward == 0.0

    def test_none_coverage_treated_as_zero(self):
        result = compute_reward(_exec(passed=2, coverage=None), previous_coverage=None)
        assert result.coverage_gain == 0.0


# -- Validity penalty


class TestValidityPenalty:
    def test_errors_penalised(self):
        result = compute_reward(_exec(passed=2, errors=2, coverage=50.0))
        assert result.invalid_tests == 2
        assert result.validity_penalty == -1.0  # 2 * -0.5

    def test_no_errors_no_penalty(self):
        result = compute_reward(_exec(passed=4, coverage=80.0))
        assert result.validity_penalty == 0.0

    def test_execution_error_penalised(self):
        result = compute_reward(_exec(execution_error="Timeout after 60 seconds"))
        assert result.validity_penalty == -0.5
        assert result.total == -0.5


# -- Redundancy penalty


class TestRedundancyPenalty:
    def test_all_pass_no_coverage_gain_no_bugs(self):
        result = compute_reward(_exec(passed=4, coverage=60.0), previous_coverage=60.0)
        assert result.redundant_tests == 4
        assert result.redundancy_penalty == -0.8  # 4 * -0.2

    def test_no_redundancy_when_bugs_found(self):
        result = compute_reward(_exec(passed=3, failed=1, coverage=60.0), previous_coverage=60.0)
        assert result.redundant_tests == 0
        assert result.redundancy_penalty == 0.0

    def test_no_redundancy_when_coverage_gained(self):
        result = compute_reward(_exec(passed=4, coverage=80.0), previous_coverage=60.0)
        assert result.redundant_tests == 0
        assert result.redundancy_penalty == 0.0


# -- Total reward


class TestTotalReward:
    def test_combined_reward(self):
        result = compute_reward(_exec(passed=3, failed=1, coverage=70.0), previous_coverage=50.0)
        expected = 1.0 + (20.0 * 0.5) + 0.0 + 0.0  # bug + coverage + no penalty
        assert result.total == expected

    def test_zero_tests_gives_zero(self):
        result = compute_reward(_exec())
        assert result.total == 0.0

    def test_all_invalid_gives_negative(self):
        result = compute_reward(_exec(errors=3, coverage=0.0))
        assert result.total < 0


# -- Custom weights


class TestCustomWeights:
    def test_custom_bug_weight(self):
        w = RewardWeights(bug_found=2.0)
        result = compute_reward(_exec(passed=2, failed=1, coverage=50.0), weights=w)
        assert result.bug_reward == 2.0

    def test_custom_coverage_weight(self):
        w = RewardWeights(coverage_gain_per_point=1.0)
        result = compute_reward(_exec(passed=2, coverage=30.0), previous_coverage=None, weights=w)
        assert result.coverage_reward == 30.0  # 30 * 1.0

    def test_zero_weights(self):
        w = RewardWeights(bug_found=0.0, coverage_gain_per_point=0.0, invalid_test=0.0, redundant_test=0.0)
        result = compute_reward(_exec(passed=2, failed=1, errors=1, coverage=50.0), weights=w)
        assert result.total == 0.0
