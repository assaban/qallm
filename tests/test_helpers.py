"""Tests for adapter helper functions (T-012)."""

from pathlib import Path

from qallm.adapters.helpers import copy_file_to_dir, copy_tree


class TestCopyFileToDir:
    def test_copies_file(self, tmp_path: Path):
        src = tmp_path / "src" / "file.py"
        src.parent.mkdir()
        src.write_text("content", encoding="utf-8")

        dst_dir = tmp_path / "dst"
        result = copy_file_to_dir(src, dst_dir)

        assert result.exists()
        assert result.read_text(encoding="utf-8") == "content"
        assert result.name == "file.py"

    def test_creates_destination_directory(self, tmp_path: Path):
        src = tmp_path / "file.py"
        src.write_text("x", encoding="utf-8")

        dst_dir = tmp_path / "deep" / "nested" / "dir"
        copy_file_to_dir(src, dst_dir)

        assert (dst_dir / "file.py").exists()


class TestCopyTree:
    def test_copies_full_tree(self, tmp_path: Path):
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "a.py").write_text("a", encoding="utf-8")
        (src / "sub" / "b.py").write_text("b", encoding="utf-8")
        (src / "data.csv").write_text("c", encoding="utf-8")

        dst = tmp_path / "dst"
        copy_tree(src, dst)

        assert (dst / "a.py").read_text(encoding="utf-8") == "a"
        assert (dst / "sub" / "b.py").read_text(encoding="utf-8") == "b"
        assert (dst / "data.csv").read_text(encoding="utf-8") == "c"

    def test_copies_only_matching_patterns(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("py", encoding="utf-8")
        (src / "notebook.ipynb").write_text("{}", encoding="utf-8")
        (src / "data.csv").write_text("csv", encoding="utf-8")

        dst = tmp_path / "dst"
        copy_tree(src, dst, patterns=("*.py", "*.ipynb"))

        assert (dst / "main.py").exists()
        assert (dst / "notebook.ipynb").exists()
        assert not (dst / "data.csv").exists()

    def test_handles_empty_directory(self, tmp_path: Path):
        src = tmp_path / "empty"
        src.mkdir()
        dst = tmp_path / "dst"

        copy_tree(src, dst)

        assert dst.exists()
        assert list(dst.iterdir()) == []
