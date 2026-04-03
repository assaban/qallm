from qallm.adapters.detector import InputKind
from qallm.adapters.factory import AdapterFactory
from qallm.adapters.git_adapter import GitRepoAdapter
from qallm.adapters.local_adapter import PythonDirectoryAdapter, PythonFileAdapter
from qallm.adapters.notebook_adapter import NotebookFileAdapter
from qallm.adapters.zip_archive_adapter import ZipArchiveAdapter


def test_factory_returns_python_file_adapter():
    assert isinstance(AdapterFactory.create(InputKind.PYTHON_FILE), PythonFileAdapter)


def test_factory_returns_python_dir_adapter():
    assert isinstance(AdapterFactory.create(InputKind.PYTHON_DIR), PythonDirectoryAdapter)


def test_factory_returns_notebook_adapter():
    assert isinstance(AdapterFactory.create(InputKind.NOTEBOOK), NotebookFileAdapter)


def test_factory_returns_zip_adapter():
    assert isinstance(AdapterFactory.create(InputKind.ZIP_ARCHIVE), ZipArchiveAdapter)


def test_factory_returns_git_adapter():
    assert isinstance(AdapterFactory.create(InputKind.GIT_URL), GitRepoAdapter)