from __future__ import annotations

import re
import shutil

from git import Repo

from qallm.session.workspace import SessionService


class RepoService:
    @staticmethod
    def normalize_git_url(url: str) -> str:
        """
        Support both HTTPS and SSH-ish GitHub URLs.
        In containers, SSH keys are often missing, so prefer HTTPS.
        """
        u = url.strip()

        # git@github.com:Owner/Repo.git -> https://github.com/Owner/Repo.git
        m = re.match(r"^git@github\.com:(.+)$", u)
        if m:
            return f"https://github.com/{m.group(1)}"

        return u

    @staticmethod
    def clone_into_session(session_id: str, git_url: str) -> None:
        dest = SessionService.workspace_raw_dir(session_id)
        dest.mkdir(parents=True, exist_ok=True)

        # Ensure empty
        if any(dest.iterdir()):
            shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)

        url = RepoService.normalize_git_url(git_url)

        # Shallow clone for speed
        Repo.clone_from(url, dest, depth=1)

        # Optional: remove .git directory (keeps workspace clean)
        git_dir = dest / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)
