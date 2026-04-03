from __future__ import annotations

from qallm.adapters.base import InputAdapter
from qallm.session.repo_service import RepoService
from qallm.session.workspace import SessionService


class GitRepoAdapter(InputAdapter):
    """Ingest a remote Git repository into a QALLM session workspace."""

    def ingest(self, input_value: str) -> str:
        repo_url = input_value.strip()

        if not repo_url:
            raise ValueError("Git repository URL cannot be empty")

        session_id = SessionService.create_session(
            source_type="github",
            github_url=repo_url,
        )
        RepoService.clone_into_session(session_id, repo_url)
        return session_id