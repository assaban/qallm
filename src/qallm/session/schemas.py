from typing import Literal

from pydantic import BaseModel


class SessionConfig(BaseModel):
    source_type: Literal["upload", "github"]
    github_url: str | None = None

    include: list[str] = ["**/*.py"]
    exclude: list[str] = [
        "__MACOSX",
        "**/._*",
        "**/.DS_Store",
        ".venv",
        "venv",
        "node_modules",
        ".git",
    ]

    analyzers: list[str] = ["bandit", "ruff", "radon", "trufflehog"]

    radon_cc_threshold: int = 10
