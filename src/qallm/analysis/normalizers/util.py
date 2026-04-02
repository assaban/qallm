from pathlib import Path


def get_snippet(workspace: Path, rel_file: str, line: int | None, context: int = 2) -> str | None:
    if not rel_file or not line or line < 1:
        return None

    fp = workspace / rel_file
    if not fp.exists() or not fp.is_file():
        return None

    try:
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, line - context)
        end = min(len(lines), line + context)
        chunk = []
        for i in range(start, end + 1):
            prefix = ">> " if i == line else "   "
            chunk.append(f"{prefix}{i:>4}: {lines[i - 1]}")
        return "\n".join(chunk)
    except Exception:
        return None


def get_rel_path(workspace: Path, filename: str) -> str:
    """
    Convert a tool-reported filename to a workspace-relative posix path.

    Handles three cases:
    1. Absolute path inside workspace  → strip workspace prefix
    2. Relative path with ./           → strip leading ./
    3. Fallback                        → return cleaned posix path
    """
    if not filename:
        return ""
    try:
        f = Path(filename)
        ws = workspace.resolve()

        # Case 1: absolute path → resolve and strip workspace prefix
        if f.is_absolute():
            return f.resolve().relative_to(ws).as_posix()

        # Case 2: relative path that might contain workspace components
        # (e.g. tools running from different cwd)
        f_resolved = (workspace / f).resolve()
        if str(f_resolved).startswith(str(ws)):
            return f_resolved.relative_to(ws).as_posix()

        # Case 3: already relative, just clean up
        return f.as_posix().lstrip("./")
    except Exception:
        # Last resort: strip common junk and return as-is
        return Path(filename).as_posix().lstrip("./")
