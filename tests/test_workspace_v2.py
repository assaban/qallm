"""Tests for T-038 workspace restructure."""

import json
from pathlib import Path

from qallm.session.workspace import SessionService


def _create_session(isolated_data_dir) -> str:
    sid = SessionService.create_session(source_type="python_file", github_url=None)
    original = SessionService.original_dir(sid)
    original.mkdir(parents=True, exist_ok=True)
    (original / "main.py").write_text("def add(a, b):\\n    return a + b\\n")
    (original / "utils.py").write_text("def helper():\\n    return 42\\n")
    return sid


class TestNewLayout:
    def test_original_dir(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        assert SessionService.original_dir(sid).exists()
        assert (SessionService.original_dir(sid) / "main.py").exists()

    def test_backward_compat_raw(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        assert SessionService.workspace_raw_dir(sid) == SessionService.original_dir(sid)

    def test_current_round_zero(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        assert SessionService.current_round(sid) == 0

    def test_next_round_creates_structure(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        r = SessionService.next_round(sid)
        assert r == 1
        rd = SessionService.round_dir(sid, 1)
        assert rd.exists()
        assert (rd / "repaired_code").exists()
        assert (rd / "generated_tests").exists()
        assert (rd / "reports").exists()

    def test_next_round_increments(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        assert SessionService.next_round(sid) == 1
        assert SessionService.next_round(sid) == 2
        assert SessionService.next_round(sid) == 3
        assert SessionService.current_round(sid) == 3

    def test_code_dir_for_round(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        assert SessionService.code_dir_for_round(sid, 0) == SessionService.original_dir(sid)

        SessionService.next_round(sid)
        r1_code = SessionService.round_repaired_code_dir(sid, 1)
        assert SessionService.code_dir_for_round(sid, 1) == r1_code

    def test_workspace_active_returns_latest(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        # No rounds yet: returns original
        assert SessionService.workspace_active_dir(sid) == SessionService.original_dir(sid)

        # After creating round 1: returns round_01/repaired_code
        SessionService.next_round(sid)
        assert "round_01/repaired_code" in str(SessionService.workspace_active_dir(sid))

    def test_list_rounds(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        rounds = SessionService.list_rounds(sid)
        assert len(rounds) == 1  # only original
        assert rounds[0]["round"] == 0
        assert rounds[0]["label"] == "Original"

        SessionService.next_round(sid)
        SessionService.next_round(sid)
        rounds = SessionService.list_rounds(sid)
        assert len(rounds) == 3  # original + round_01 + round_02

    def test_list_workspace_files(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        files = SessionService.list_workspace_files(sid)
        assert "main.py" in files
        assert "utils.py" in files

    def test_baseline_dirs(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        reports = SessionService.baseline_reports_dir(sid)
        tests = SessionService.baseline_generated_tests_dir(sid)
        assert reports.exists()
        assert tests.exists()

    def test_round_reports_dir(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        SessionService.next_round(sid)
        reports = SessionService.round_reports_dir(sid, 1)
        assert reports.exists()
        assert "round_01/reports" in str(reports)

    def test_reports_dir_backward_compat(self, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        # No rounds: returns baseline reports
        r0 = SessionService.reports_dir(sid)
        assert "baseline_tests/reports" in str(r0)

        # After round: returns round reports
        SessionService.next_round(sid)
        r1 = SessionService.reports_dir(sid)
        assert "round_01/reports" in str(r1)


class TestComparison:
    def test_generate_comparison(self, isolated_data_dir):
        from qallm.analysis.comparison import generate_comparison

        sid = _create_session(isolated_data_dir)

        # Write baseline metrics
        baseline_reports = SessionService.baseline_reports_dir(sid)
        (baseline_reports / "paper_metrics.json").write_text(
            json.dumps({"cs": 8, "mi": 74.0, "codu": 33.0, "code": 45.0, "loc": 146, "cc": 0.0})
        )

        # Create round 1 with improved metrics
        SessionService.next_round(sid)
        round_reports = SessionService.round_reports_dir(sid, 1)
        (round_reports / "paper_metrics.json").write_text(
            json.dumps({"cs": 6, "mi": 79.0, "codu": 0.0, "code": 30.0, "loc": 165, "cc": 1.1})
        )

        comp = generate_comparison(sid, 1)

        assert comp["round"] == 1
        assert "vs_baseline" in comp
        assert comp["vs_baseline"]["cs_delta"] == -2  # improved
        assert comp["vs_baseline"]["mi_delta"] == 5.0  # improved
        assert comp["vs_baseline"]["codu_delta"] == -33.0  # improved

    def test_comparison_vs_previous_round(self, isolated_data_dir):
        from qallm.analysis.comparison import generate_comparison

        sid = _create_session(isolated_data_dir)

        # Baseline
        baseline = SessionService.baseline_reports_dir(sid)
        (baseline / "paper_metrics.json").write_text(
            json.dumps({"cs": 10, "mi": 70.0, "codu": 30.0, "code": 40.0, "loc": 100, "cc": 2.0})
        )

        # Round 1
        SessionService.next_round(sid)
        r1 = SessionService.round_reports_dir(sid, 1)
        (r1 / "paper_metrics.json").write_text(
            json.dumps({"cs": 7, "mi": 75.0, "codu": 10.0, "code": 35.0, "loc": 120, "cc": 1.5})
        )

        # Round 2
        SessionService.next_round(sid)
        r2 = SessionService.round_reports_dir(sid, 2)
        (r2 / "paper_metrics.json").write_text(
            json.dumps({"cs": 5, "mi": 80.0, "codu": 0.0, "code": 30.0, "loc": 130, "cc": 1.2})
        )

        comp = generate_comparison(sid, 2)

        assert "vs_baseline" in comp
        assert "vs_previous" in comp
        assert comp["vs_baseline"]["cs_delta"] == -5
        assert comp["vs_previous"]["cs_delta"] == -2


class TestVersionAPI:
    def test_list_rounds_api(self, client, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        r = client.get(f"/api/session/{sid}/versions")
        assert r.status_code == 200
        data = r.json()
        assert "versions" in data

    def test_restore_is_noop(self, client, isolated_data_dir):
        sid = _create_session(isolated_data_dir)
        r = client.post(f"/api/session/{sid}/restore/0")
        assert r.status_code == 200
