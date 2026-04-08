"""Tests for the Git repository adapter (T-012).

Clone operations are mocked to avoid network dependency in CI.
"""

from unittest.mock import patch

import pytest

from qallm.adapters.git_adapter import GitRepoAdapter
from qallm.session.workspace import SessionService


class TestGitRepoAdapter:
    def test_ingest_creates_session(self):
        """Verify session is created even if clone is mocked."""
        with patch("qallm.session.repo_service.RepoService.clone_into_session") as mock_clone:
            adapter = GitRepoAdapter()
            session_id = adapter.ingest("https://github.com/user/repo")

            assert SessionService.session_exists(session_id)
            mock_clone.assert_called_once_with(session_id, "https://github.com/user/repo")

    def test_ingest_strips_whitespace(self):
        with patch("qallm.session.repo_service.RepoService.clone_into_session"):
            adapter = GitRepoAdapter()
            session_id = adapter.ingest("  https://github.com/user/repo  ")
            assert SessionService.session_exists(session_id)

    def test_ingest_rejects_empty_url(self):
        adapter = GitRepoAdapter()
        with pytest.raises(ValueError, match="cannot be empty"):
            adapter.ingest("")

    def test_ingest_rejects_whitespace_only(self):
        adapter = GitRepoAdapter()
        with pytest.raises(ValueError, match="cannot be empty"):
            adapter.ingest("   ")

    def test_session_stores_github_url(self):
        url = "https://github.com/user/repo"
        with patch("qallm.session.repo_service.RepoService.clone_into_session"):
            adapter = GitRepoAdapter()
            session_id = adapter.ingest(url)

            info = SessionService.get_session_info(session_id)
            assert info is not None
            assert info["config"]["github_url"] == url
