from pathlib import Path

from qallm.adapters.detector import InputKind, detect_input


def test_detect_python_file(tmp_path: Path):
    path = tmp_path / "demo.py"
    path.write_text("print('hi')\n", encoding="utf-8")

    detected = detect_input(str(path))

    assert detected.kind == InputKind.PYTHON_FILE
    assert detected.value == str(path.resolve())


def test_detect_notebook(tmp_path: Path):
    path = tmp_path / "demo.ipynb"
    path.write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        encoding="utf-8",
    )

    detected = detect_input(str(path))

    assert detected.kind == InputKind.NOTEBOOK


def test_detect_zip(tmp_path: Path):
    path = tmp_path / "demo.zip"
    path.write_bytes(b"PK\x03\x04")

    detected = detect_input(str(path))

    assert detected.kind == InputKind.ZIP_ARCHIVE


def test_detect_directory(tmp_path: Path):
    detected = detect_input(str(tmp_path))
    assert detected.kind == InputKind.PYTHON_DIR


def test_detect_git_url():
    detected = detect_input("https://github.com/assaban/qallm")
    assert detected.kind == InputKind.GIT_URL