import zipfile
from pathlib import Path

from qallm.adapters.zip_archive_adapter import ZipArchiveAdapter
from qallm.session.workspace import SessionService


def test_zip_archive_adapter_extracts_files(tmp_path: Path):
    src_py = tmp_path / "demo.py"
    src_py.write_text("print('hello')\n", encoding="utf-8")

    src_nb = tmp_path / "demo.ipynb"
    src_nb.write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        encoding="utf-8",
    )

    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(src_py, arcname="demo.py")
        zf.write(src_nb, arcname="nested/demo.ipynb")

    adapter = ZipArchiveAdapter()
    session_id = adapter.ingest(str(archive))

    raw_dir = SessionService.workspace_raw_dir(session_id)
    assert (raw_dir / "demo.py").exists()
    assert (raw_dir / "nested" / "demo.ipynb").exists()


def test_zip_archive_adapter_rejects_non_zip(tmp_path: Path):
    path = tmp_path / "not_zip.txt"
    path.write_text("hello", encoding="utf-8")

    adapter = ZipArchiveAdapter()

    try:
        adapter.ingest(str(path))
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Expected a .zip file" in str(exc)


def test_zip_archive_adapter_blocks_zip_slip(tmp_path: Path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.py", "print('owned')\n")

    adapter = ZipArchiveAdapter()

    try:
        adapter.ingest(str(archive))
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unsafe ZIP member path detected" in str(exc)