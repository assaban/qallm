"""Tests for T-022 pipeline integration: CLI commands and API routes.

Tests mock the LLM and executor to avoid real API calls.
"""

import json
import textwrap
from unittest.mock import MagicMock, patch

from qallm.llm.base import LLMResponse
from qallm.session.workspace import SessionService
from qallm.verification.models import ExecutionResult, TestDetail

SAMPLE_SOURCE = textwrap.dedent("""\
    def add(a, b):
        return a + b
""")

VALID_TEST_CODE = textwrap.dedent("""\
    import pytest
    from source_module import add

    def test_add_basic():
        assert add(1, 2) == 3

    def test_add_zero():
        assert add(0, 0) == 0
""")


def _mock_execution(**kwargs):
    defaults = dict(
        passed=2,
        failed=0,
        errors=0,
        total=2,
        coverage_percent=80.0,
        duration_seconds=0.5,
        test_details=[
            TestDetail(name="test_add_basic", status="passed"),
            TestDetail(name="test_add_zero", status="passed"),
        ],
    )
    defaults.update(kwargs)
    return ExecutionResult(**defaults)


def _make_fake_llm():
    mock_llm = MagicMock()
    mock_llm.name.return_value = "fake"
    mock_llm.is_configured.return_value = True
    mock_llm.chat.return_value = LLMResponse(
        content=VALID_TEST_CODE,
        error=None,
        input_tokens=50,
        output_tokens=100,
        model="fake",
        provider="fake",
    )
    return mock_llm


def _make_fake_registry(llm):
    registry = MagicMock()
    registry.pick.return_value = llm
    registry.list.return_value = ["fake"]
    registry.list_configured.return_value = ["fake"]
    return registry


def _create_session_with_py(source: str = SAMPLE_SOURCE) -> str:
    session_id = SessionService.create_session(source_type="python_file", github_url=None)
    # Put files in both raw and active workspace (active takes priority in CLI)
    for dirname in [SessionService.workspace_raw_dir(session_id), SessionService.workspace_active_dir(session_id)]:
        dirname.mkdir(parents=True, exist_ok=True)
        (dirname / "source_module.py").write_text(source, encoding="utf-8")
    return session_id


# -- CLI: generate-tests


class TestCLIGenerateTests:
    @patch("qallm.verification.loop.run_tests")
    @patch("qallm.repair.containers.build_llm_registry")
    def test_generate_tests_with_session_flag(self, mock_build_reg, mock_run, tmp_path, isolated_data_dir):
        mock_run.return_value = _mock_execution()
        llm = _make_fake_llm()
        mock_build_reg.return_value = _make_fake_registry(llm)

        session_id = _create_session_with_py()
        output_file = tmp_path / "result.json"

        from qallm.cli import main

        with patch(
            "sys.argv",
            ["qallm", "generate-tests", session_id, "--session", "--rounds", "1", "-o", str(output_file)],
        ):
            main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["session_id"] == session_id
        assert data["total_functions"] >= 1


# -- CLI: full


class TestCLIFull:
    @patch("qallm.verification.loop.run_tests")
    @patch("qallm.repair.containers.build_llm_registry")
    def test_full_pipeline_produces_combined_report(self, mock_build_reg, mock_run, tmp_path, isolated_data_dir):
        mock_run.return_value = _mock_execution()
        llm = _make_fake_llm()
        mock_build_reg.return_value = _make_fake_registry(llm)

        py_file = tmp_path / "code.py"
        py_file.write_text(SAMPLE_SOURCE, encoding="utf-8")
        output_file = tmp_path / "full_result.json"

        from qallm.cli import main

        with patch(
            "sys.argv",
            ["qallm", "full", str(py_file), "--rounds", "1", "--yes", "-o", str(output_file)],
        ):
            main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "static_analysis" in data
        assert "verification" in data
        assert data["verification"]["total_functions"] >= 1


# -- API: /api/verification


class TestVerificationAPI:
    def test_models_endpoint(self, client):
        r = client.get("/api/verification/models")
        assert r.status_code == 200
        data = r.json()
        assert "available" in data
        assert "configured" in data

    def test_run_rejects_missing_session(self, client):
        r = client.post(
            "/api/verification/run",
            json={"session_id": "nonexistent", "rounds": 1},
        )
        assert r.status_code == 404

    @patch("qallm.verification.loop.run_tests")
    @patch("qallm.api.verification_routes._llm_registry")
    def test_run_on_session(self, mock_registry, mock_run, client, isolated_data_dir):
        mock_run.return_value = _mock_execution()
        llm = _make_fake_llm()
        mock_registry.pick.return_value = llm
        mock_registry.list.return_value = ["fake"]
        mock_registry.list_configured.return_value = ["fake"]

        session_id = _create_session_with_py()

        active = SessionService.workspace_active_dir(session_id)
        active.mkdir(parents=True, exist_ok=True)
        (active / "source_module.py").write_text(SAMPLE_SOURCE)

        r = client.post(
            "/api/verification/run",
            json={"session_id": session_id, "model": "fake", "rounds": 1},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["total_functions"] >= 1
        assert data["session_id"] == session_id
