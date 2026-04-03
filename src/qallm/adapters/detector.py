from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class InputKind(str, Enum):
    NOTEBOOK = "notebook"
    PYTHON_FILE = "python_file"
    PYTHON_DIR = "python_dir"
    ZIP_ARCHIVE = "zip_archive"
    GIT_URL = "git_url"


@dataclass(frozen=True)
class DetectedInput:
    kind: InputKind
    value: str


def is_git_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.netloc or "").lower()
    return "github.com" in host


def detect_input(value: str) -> DetectedInput:
    if is_git_url(value):
        return DetectedInput(InputKind.GIT_URL, value)

    path = Path(value).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Input does not exist: {value}")

    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".ipynb":
            return DetectedInput(InputKind.NOTEBOOK, str(path))
        if suffix == ".py":
            return DetectedInput(InputKind.PYTHON_FILE, str(path))
        if suffix == ".zip":
            return DetectedInput(InputKind.ZIP_ARCHIVE, str(path))

    if path.is_dir():
        return DetectedInput(InputKind.PYTHON_DIR, str(path))

    raise ValueError("Unsupported input. Expected .ipynb, .py, .zip, directory, or GitHub URL.")
