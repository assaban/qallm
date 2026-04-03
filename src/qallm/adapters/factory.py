from __future__ import annotations

from qallm.adapters.base import InputAdapter
from qallm.adapters.detector import InputKind
from qallm.adapters.git_adapter import GitRepoAdapter
from qallm.adapters.local_adapter import PythonDirectoryAdapter, PythonFileAdapter
from qallm.adapters.notebook_adapter import NotebookFileAdapter
from qallm.adapters.zip_archive_adapter import ZipArchiveAdapter


class AdapterFactory:
    @staticmethod
    def create(kind: InputKind) -> InputAdapter:
        if kind == InputKind.PYTHON_FILE:
            return PythonFileAdapter()
        if kind == InputKind.PYTHON_DIR:
            return PythonDirectoryAdapter()
        if kind == InputKind.NOTEBOOK:
            return NotebookFileAdapter()
        if kind == InputKind.ZIP_ARCHIVE:
            return ZipArchiveAdapter()
        if kind == InputKind.GIT_URL:
            return GitRepoAdapter()

        raise ValueError(f"No adapter available for input kind: {kind}")
