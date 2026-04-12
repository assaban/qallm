"""Tests for repair history snapshots (T-025).

Tests SessionService snapshot/restore methods and API endpoints.
"""

from qallm.session.workspace import SessionService


def _create_session_with_files(isolated_data_dir) -> str:
    """Create a session with sample Python files in workspace."""
    session_id = SessionService.create_session(source_type="python_file", github_url=None)

    # Put files in active workspace
    workspace = SessionService.workspace_active_dir(session_id)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (workspace / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    # Also put in raw
    raw = SessionService.workspace_raw_dir(session_id)
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (raw / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    return session_id


class TestSnapshotWorkspace:
    def test_creates_round_01(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        round_num = SessionService.snapshot_workspace(session_id)

        assert round_num == 1
        round_dir = SessionService.repair_history_dir(session_id) / "round_01"
        assert round_dir.exists()
        assert (round_dir / "main.py").exists()
        assert (round_dir / "utils.py").exists()

    def test_increments_round_number(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)

        r1 = SessionService.snapshot_workspace(session_id)
        r2 = SessionService.snapshot_workspace(session_id)
        r3 = SessionService.snapshot_workspace(session_id)

        assert r1 == 1
        assert r2 == 2
        assert r3 == 3

    def test_snapshot_preserves_content(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)

        # Snapshot original
        SessionService.snapshot_workspace(session_id)

        # Modify workspace
        workspace = SessionService.workspace_active_dir(session_id)
        (workspace / "main.py").write_text("def add(a, b):\n    return a + b + 0  # repaired\n")

        # Snapshot modified
        SessionService.snapshot_workspace(session_id)

        # Round 1 should have original content
        round_1 = SessionService.repair_history_dir(session_id) / "round_01" / "main.py"
        assert "# repaired" not in round_1.read_text()

        # Round 2 should have modified content
        round_2 = SessionService.repair_history_dir(session_id) / "round_02" / "main.py"
        assert "# repaired" in round_2.read_text()


class TestListRepairRounds:
    def test_lists_original_only_when_no_repairs(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        rounds = SessionService.list_repair_rounds(session_id)

        assert len(rounds) == 2  # original + current
        assert rounds[0]["round"] == 0
        assert "Original" in rounds[0]["label"]
        assert "Current" in rounds[-1]["label"]

    def test_lists_repair_rounds(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        SessionService.snapshot_workspace(session_id)
        SessionService.snapshot_workspace(session_id)

        rounds = SessionService.list_repair_rounds(session_id)

        assert len(rounds) == 4  # original + round_01 + round_02 + current
        assert rounds[0]["round"] == 0
        assert rounds[1]["round"] == 1
        assert rounds[2]["round"] == 2

    def test_file_counts_are_correct(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        SessionService.snapshot_workspace(session_id)

        rounds = SessionService.list_repair_rounds(session_id)
        # All versions should have 2 Python files
        for v in rounds:
            assert v["files"] == 2


class TestRestoreRepairRound:
    def test_restore_original(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)

        # Modify workspace
        workspace = SessionService.workspace_active_dir(session_id)
        (workspace / "main.py").write_text("MODIFIED")

        # Restore original
        success = SessionService.restore_repair_round(session_id, 0)
        assert success is True
        assert (workspace / "main.py").read_text().startswith("def add")

    def test_restore_specific_round(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)

        # Snapshot, modify, snapshot again
        SessionService.snapshot_workspace(session_id)
        workspace = SessionService.workspace_active_dir(session_id)
        (workspace / "main.py").write_text("ROUND_1_REPAIRED")
        SessionService.snapshot_workspace(session_id)
        (workspace / "main.py").write_text("ROUND_2_REPAIRED")

        # Restore round 2 (which has ROUND_1_REPAIRED)
        success = SessionService.restore_repair_round(session_id, 2)
        assert success is True
        assert (workspace / "main.py").read_text() == "ROUND_1_REPAIRED"

    def test_restore_nonexistent_round_returns_false(self, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        success = SessionService.restore_repair_round(session_id, 99)
        assert success is False


class TestVersionAPI:
    def test_list_versions(self, client, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        r = client.get(f"/api/session/{session_id}/versions")
        assert r.status_code == 200
        data = r.json()
        assert "versions" in data
        assert len(data["versions"]) >= 2

    def test_restore_original(self, client, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)

        # Modify workspace
        workspace = SessionService.workspace_active_dir(session_id)
        (workspace / "main.py").write_text("CHANGED")

        r = client.post(f"/api/session/{session_id}/restore/0")
        assert r.status_code == 200
        assert r.json()["restored_round"] == 0

        # Verify restored
        assert (workspace / "main.py").read_text().startswith("def add")

    def test_restore_bad_round_returns_404(self, client, isolated_data_dir):
        session_id = _create_session_with_files(isolated_data_dir)
        r = client.post(f"/api/session/{session_id}/restore/99")
        assert r.status_code == 404
