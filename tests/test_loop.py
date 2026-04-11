"""Tests for the RL feedback loop (T-017).

Uses a mock LLM and patches the executor to avoid real subprocess calls.
This tests the orchestration logic: round sequencing, feedback prompt
construction, cumulative metric tracking, early stopping, and session output.
"""

import textwrap
from unittest.mock import patch

from qallm.llm.base import LLMModel, LLMResponse, TokenTracker
from qallm.verification.loop import TestGenerationLoop, save_session
from qallm.verification.models import (
    ExecutionResult,
    FunctionInfo,
    TestDetail,
)

# -- Helpers


VALID_TEST_CODE = textwrap.dedent("""\
    import pytest
    from source_module import compute_mean

    def test_normal():
        assert compute_mean([1, 2, 3]) == 2.0

    def test_empty():
        with pytest.raises(ZeroDivisionError):
            compute_mean([])
""")

SOURCE_CODE = textwrap.dedent("""\
    def compute_mean(data):
        return sum(data) / len(data)
""")


def _make_func() -> FunctionInfo:
    return FunctionInfo(
        name="compute_mean",
        source="def compute_mean(data):\n    return sum(data) / len(data)\n",
        docstring="Compute the arithmetic mean.",
        args=[("data", None)],
        lineno=1,
        filepath="source_module.py",
    )


class RoundConfigLLM(LLMModel):
    """Mock LLM that returns different content per call.

    Takes a list of response strings. Each chat() call pops the next one.
    If the list is exhausted, returns the last response again.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    def name(self) -> str:
        return "round-config-model"

    def is_configured(self) -> bool:
        return True

    def chat(self, system: str, user: str, tracker: TokenTracker | None = None) -> LLMResponse:
        idx = min(self._call_count, len(self._responses) - 1)
        content = self._responses[idx]
        self._call_count += 1

        resp = LLMResponse(
            content=content,
            input_tokens=50,
            output_tokens=100,
            model="round-config-model",
            provider="fake",
        )
        if tracker:
            tracker.record(resp)
        return resp


def _mock_execution(
    passed: int = 2,
    failed: int = 1,
    coverage: float = 60.0,
) -> ExecutionResult:
    details = []
    for i in range(passed):
        details.append(TestDetail(name=f"test_pass_{i}", status="passed"))
    for i in range(failed):
        details.append(TestDetail(name=f"test_fail_{i}", status="failed", message="AssertionError"))

    return ExecutionResult(
        passed=passed,
        failed=failed,
        errors=0,
        total=passed + failed,
        coverage_percent=coverage,
        test_details=details,
        duration_seconds=0.5,
    )


# -- TestGenerationLoop tests


class TestTestGenerationLoopBasic:
    @patch("qallm.verification.loop.run_tests")
    def test_runs_correct_number_of_rounds(self, mock_run):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert len(session.rounds) == 3

    @patch("qallm.verification.loop.run_tests")
    def test_first_round_uses_oracle_prompt(self, mock_run):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=1)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.rounds[0].round_number == 1
        assert session.rounds[0].generated_test.is_valid is True

    @patch("qallm.verification.loop.run_tests")
    def test_session_metadata(self, mock_run):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=1)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.function_name == "compute_mean"
        assert session.oracle == "crash"
        assert session.model == "round-config-model"
        assert session.total_rounds == 1

    @patch("qallm.verification.loop.run_tests")
    def test_tracks_cumulative_tokens(self, mock_run):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.total_input_tokens == 150  # 50 * 3
        assert session.total_output_tokens == 300  # 100 * 3


class TestTestGenerationLoopRewards:
    @patch("qallm.verification.loop.run_tests")
    def test_each_round_has_reward(self, mock_run):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        for r in session.rounds:
            assert r.reward is not None
            assert isinstance(r.reward.total, float)

    @patch("qallm.verification.loop.run_tests")
    def test_first_round_gets_full_coverage_reward(self, mock_run):
        mock_run.return_value = _mock_execution(coverage=60.0)
        llm = RoundConfigLLM([VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=1)
        session = loop.run(_make_func(), SOURCE_CODE)

        reward = session.rounds[0].reward
        assert reward.coverage_gain == 60.0
        assert reward.coverage_reward == 30.0  # 60 * 0.5

    @patch("qallm.verification.loop.run_tests")
    def test_subsequent_rounds_only_reward_new_coverage(self, mock_run):
        # Round 1: 60%, Round 2: 80% (20% gain), Round 3: 80% (0% gain)
        mock_run.side_effect = [
            _mock_execution(coverage=60.0),
            _mock_execution(coverage=80.0),
            _mock_execution(coverage=80.0),
        ]
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.rounds[0].reward.coverage_gain == 60.0
        assert session.rounds[1].reward.coverage_gain == 20.0
        assert session.rounds[2].reward.coverage_gain == 0.0


class TestTestGenerationLoopCumulative:
    @patch("qallm.verification.loop.run_tests")
    def test_tracks_cumulative_coverage(self, mock_run):
        mock_run.side_effect = [
            _mock_execution(coverage=40.0),
            _mock_execution(coverage=70.0),
            _mock_execution(coverage=50.0),  # coverage drops, but best stays 70
        ]
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.rounds[0].cumulative_coverage == 40.0
        assert session.rounds[1].cumulative_coverage == 70.0
        assert session.rounds[2].cumulative_coverage == 70.0  # best so far

    @patch("qallm.verification.loop.run_tests")
    def test_tracks_cumulative_bugs(self, mock_run):
        mock_run.side_effect = [
            _mock_execution(failed=1, coverage=50.0),
            _mock_execution(failed=2, coverage=60.0),
            _mock_execution(failed=0, coverage=65.0),
        ]
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.rounds[0].cumulative_bugs == 1
        assert session.rounds[1].cumulative_bugs == 3
        assert session.rounds[2].cumulative_bugs == 3


class TestTestGenerationLoopLearningCurve:
    @patch("qallm.verification.loop.run_tests")
    def test_learning_curve_grows(self, mock_run):
        mock_run.side_effect = [
            _mock_execution(failed=1, coverage=40.0),
            _mock_execution(failed=0, coverage=60.0),
            _mock_execution(failed=1, coverage=80.0),
        ]
        llm = RoundConfigLLM([VALID_TEST_CODE] * 3)

        loop = TestGenerationLoop(llm, rounds=3)
        session = loop.run(_make_func(), SOURCE_CODE)

        curve = session.learning_curve
        assert len(curve) == 3
        # Cumulative rewards should generally increase
        assert curve[-1] > curve[0]

    @patch("qallm.verification.loop.run_tests")
    def test_reward_per_round_list(self, mock_run):
        mock_run.return_value = _mock_execution(failed=1, coverage=50.0)
        llm = RoundConfigLLM([VALID_TEST_CODE] * 2)

        loop = TestGenerationLoop(llm, rounds=2)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert len(session.reward_per_round) == 2
        assert all(isinstance(r, float) for r in session.reward_per_round)


class TestTestGenerationLoopEarlyStop:
    @patch("qallm.verification.loop.run_tests")
    def test_stops_at_full_coverage_with_bugs(self, mock_run):
        mock_run.return_value = _mock_execution(failed=1, coverage=100.0)
        llm = RoundConfigLLM([VALID_TEST_CODE] * 10)

        loop = TestGenerationLoop(llm, rounds=10)
        session = loop.run(_make_func(), SOURCE_CODE)

        # Should stop early since 100% coverage + bugs found
        assert len(session.rounds) < 10


class TestTestGenerationLoopInvalidTests:
    @patch("qallm.verification.loop.run_tests")
    def test_handles_invalid_generation_gracefully(self, mock_run):
        mock_run.return_value = _mock_execution()
        # First round: invalid code, second round: valid
        llm = RoundConfigLLM(["not python at all", VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=2)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert len(session.rounds) == 2
        assert session.rounds[0].generated_test.is_valid is False
        assert session.rounds[1].generated_test.is_valid is True


class TestTestGenerationLoopFeedback:
    @patch("qallm.verification.loop.run_tests")
    def test_second_round_gets_feedback_prompt(self, mock_run):
        mock_run.return_value = _mock_execution()
        call_prompts = []

        class CaptureLLM(LLMModel):
            def name(self):
                return "capture"

            def is_configured(self):
                return True

            def chat(self, system, user, tracker=None):
                call_prompts.append(user)
                resp = LLMResponse(
                    content=VALID_TEST_CODE,
                    input_tokens=10,
                    output_tokens=20,
                    model="capture",
                    provider="fake",
                )
                if tracker:
                    tracker.record(resp)
                return resp

        loop = TestGenerationLoop(CaptureLLM(), rounds=2)
        loop.run(_make_func(), SOURCE_CODE)

        # First prompt should NOT contain "Round 2" or "Improve"
        assert "Round 2" not in call_prompts[0]
        # Second prompt SHOULD contain feedback elements
        assert "Round 2" in call_prompts[1]
        assert "Improve" in call_prompts[1]
        assert "Execution results" in call_prompts[1]


class TestSaveSession:
    @patch("qallm.verification.loop.run_tests")
    def test_saves_json(self, mock_run, tmp_path):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=1)
        session = loop.run(_make_func(), SOURCE_CODE)

        out = tmp_path / "session.json"
        save_session(session, out)

        assert out.exists()
        import json

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["function_name"] == "compute_mean"
        assert len(data["rounds"]) == 1
        assert "reward" in data["rounds"][0]

    @patch("qallm.verification.loop.run_tests")
    def test_session_properties_in_json(self, mock_run, tmp_path):
        mock_run.side_effect = [
            _mock_execution(failed=1, coverage=50.0),
            _mock_execution(failed=0, coverage=70.0),
        ]
        llm = RoundConfigLLM([VALID_TEST_CODE] * 2)

        loop = TestGenerationLoop(llm, rounds=2)
        session = loop.run(_make_func(), SOURCE_CODE)

        assert session.final_coverage == 70.0
        assert session.final_bugs >= 1
        assert len(session.learning_curve) == 2


class TestPersistence:
    @patch("qallm.verification.loop.run_tests")
    def test_saves_test_code_to_persist_dir(self, mock_run, tmp_path):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE] * 2)

        loop = TestGenerationLoop(llm, rounds=2)
        persist_dir = tmp_path / "generated_tests"
        loop.run(_make_func(), SOURCE_CODE, persist_dir=persist_dir)

        assert persist_dir.exists()
        test_files = list(persist_dir.glob("*.py"))
        assert len(test_files) == 2
        assert any("round_01" in f.name for f in test_files)
        assert any("round_02" in f.name for f in test_files)

        # Verify content is actual test code
        content = test_files[0].read_text(encoding="utf-8")
        assert "def test_" in content

    @patch("qallm.verification.loop.run_tests")
    def test_no_persistence_when_persist_dir_is_none(self, mock_run, tmp_path):
        mock_run.return_value = _mock_execution()
        llm = RoundConfigLLM([VALID_TEST_CODE])

        loop = TestGenerationLoop(llm, rounds=1)
        loop.run(_make_func(), SOURCE_CODE)

        # No generated_tests dir should be created anywhere
        assert not (tmp_path / "generated_tests").exists()
