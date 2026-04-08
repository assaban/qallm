"""Additional edge case tests for the input detector (T-012)."""

from pathlib import Path

import pytest

from qallm.adapters.detector import InputKind, detect_input, is_git_url

# -- is_git_url edge cases


def test_git_url_rejects_ftp():
    assert is_git_url("ftp://github.com/user/repo") is False


def test_git_url_rejects_plain_string():
    assert is_git_url("not a url at all") is False


def test_git_url_rejects_non_github():
    assert is_git_url("https://gitlab.com/user/repo") is False


def test_git_url_accepts_https_github():
    assert is_git_url("https://github.com/user/repo") is True


def test_git_url_accepts_http_github():
    assert is_git_url("http://github.com/user/repo") is True


def test_git_url_accepts_github_with_dot_git():
    assert is_git_url("https://github.com/user/repo.git") is True


# -- detect_input edge cases


def test_detect_unsupported_file_extension(tmp_path: Path):
    f = tmp_path / "data.json"
    f.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported input"):
        detect_input(str(f))


def test_detect_nonexistent_path():
    with pytest.raises(FileNotFoundError, match="does not exist"):
        detect_input("/tmp/absolutely_does_not_exist_12345.py")


def test_detect_returns_resolved_path(tmp_path: Path):
    f = tmp_path / "script.py"
    f.write_text("x = 1", encoding="utf-8")

    result = detect_input(str(f))
    assert result.kind == InputKind.PYTHON_FILE
    assert Path(result.value).is_absolute()
