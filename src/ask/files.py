"""Decide which files in a folder are indexed and read them as lines."""

import os
import subprocess
from pathlib import Path

MAX_BYTES = 1_048_576
SNIFF_BYTES = 8192


def _is_git_root(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and Path(result.stdout.strip()).resolve() == root.resolve()


def _utf8(name: str) -> bool:
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _wanted(root: Path, rel: Path) -> bool:
    full = root / rel
    return not rel.name.startswith(".env") and not full.is_symlink() and full.is_file()


def list_files(root: Path) -> list[Path]:
    """Return sorted relative paths to index. A git root uses `git ls-files`; any other folder is walked, skipping `.git`, symlinks and `.env*` files. Names that are not valid UTF-8 are skipped."""
    if _is_git_root(root):
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
        ).stdout
        names = [os.fsdecode(n) for n in out.split(b"\0") if n]
        return sorted(p for p in map(Path, filter(_utf8, names)) if _wanted(root, p))
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(root)
            if _utf8(str(rel)) and _wanted(root, rel):
                found.append(rel)
    return sorted(found)


def read_text_lines(path: Path) -> list[str] | None:
    """Return the file's lines, or None for a symlink, a file over 1 MB, a binary file or non-UTF-8 text. Lines are split on newline with one trailing carriage return removed."""
    if path.is_symlink():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        with path.open("rb") as f:
            data = f.read(MAX_BYTES + 1)
    except OSError:
        return None
    if len(data) > MAX_BYTES or b"\0" in data[:SNIFF_BYTES]:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
