from __future__ import annotations

import shutil
from pathlib import Path


def copy_file_to_dir(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name
    shutil.copy2(src, target)
    return target


def copy_tree(
    src_dir: Path,
    dst_dir: Path,
    patterns: tuple[str, ...] | None = None,
) -> None:
    """
    Copy a directory tree into dst_dir.

    If patterns is provided, only matching files are copied.
    Relative paths are preserved.
    """
    src_dir = src_dir.resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)

    if not patterns:
        for path in src_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src_dir)
            target = dst_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return

    seen: set[Path] = set()
    for pattern in patterns:
        for path in src_dir.rglob(pattern):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = path.relative_to(src_dir)
            target = dst_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
