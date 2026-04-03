from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


SessionSourceType = Literal[
    "upload",
    "github",
    "python_file",
    "python_dir",
    "notebook",
    "zip",
]


class SessionConfig(BaseModel):
    source_type: SessionSourceType
    github_url: str | None = None