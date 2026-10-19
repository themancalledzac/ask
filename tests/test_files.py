import os
import subprocess
from pathlib import Path

import pytest

from ask.files import list_files, read_text_lines
from ask.store import add_repo, connect


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def write(root, rel, data="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data)
    return p


def test_git_repo_lists_tracked_files_only(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, ".gitignore", "ignored.txt\n")
    write(tmp_path, "a.py")
    write(tmp_path, ".github/workflows/ci.yml")
    write(tmp_path, "ignored.txt")
    write(tmp_path, "untracked.txt")
    write(tmp_path, ".env")
    write(tmp_path, "sub/.env.local")
    git(tmp_path, "add", "-f", ".gitignore", "a.py", ".github", ".env", "sub")
    git(tmp_path, "commit", "-q", "-m", "init")
    assert list_files(tmp_path) == [
        Path(".github/workflows/ci.yml"),
        Path(".gitignore"),
        Path("a.py"),
    ]


def test_git_tracked_but_gitignored_file_is_listed(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, ".gitignore", "kept.txt\n")
    write(tmp_path, "kept.txt")
    git(tmp_path, "add", "-f", ".gitignore", "kept.txt")
    git(tmp_path, "commit", "-q", "-m", "init")
    assert Path("kept.txt") in list_files(tmp_path)


def test_git_tracked_but_deleted_file_is_skipped(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, "gone.txt")
    write(tmp_path, "here.txt")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "gone.txt").unlink()
    assert list_files(tmp_path) == [Path("here.txt")]


def test_non_git_folder_skips_git_binaries_env_and_keeps_github(tmp_path):
    write(tmp_path, ".git/config")
    write(tmp_path, "logo.png", b"\x89PNG\r\n\x1a\n\x00\x00")
    write(tmp_path, ".env")
    write(tmp_path, ".env.local")
    write(tmp_path, "deep/.env.production")
    write(tmp_path, ".github/CODEOWNERS", "* @team\n")
    write(tmp_path, "src/main.py")
    found = list_files(tmp_path)
    assert Path(".github/CODEOWNERS") in found
    assert Path("src/main.py") in found
    assert not any(p.parts[0] == ".git" for p in found)
    assert not any(p.name.startswith(".env") for p in found)
    assert found == sorted(found)
    assert read_text_lines(tmp_path / "logo.png") is None


def test_symlink_is_skipped(tmp_path):
    write(tmp_path, "real.txt")
    os.symlink(tmp_path / "real.txt", tmp_path / "link.txt")
    assert list_files(tmp_path) == [Path("real.txt")]
    assert read_text_lines(tmp_path / "link.txt") is None


def test_git_symlink_is_skipped(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, "real.txt")
    os.symlink("real.txt", tmp_path / "link.txt")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    assert list_files(tmp_path) == [Path("real.txt")]


def test_subfolder_of_git_repo_is_not_a_git_root(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sub = tmp_path / "sub"
    write(sub, "a.txt")
    write(sub, "untracked.txt")
    assert list_files(sub) == [Path("a.txt"), Path("untracked.txt")]


def test_crlf_file_line_count(tmp_path):
    p = write(tmp_path, "a.txt", b"one\r\ntwo\r\nthree\r\n")
    assert read_text_lines(p) == ["one", "two", "three", ""]


def test_long_line_counts_as_one_line(tmp_path):
    p = write(tmp_path, "a.txt", "a" * 5000 + "\nb\n")
    lines = read_text_lines(p)
    assert len(lines) == 3
    assert len(lines[0]) == 5000


def test_only_one_trailing_cr_is_removed(tmp_path):
    p = write(tmp_path, "a.txt", b"x\r\r\ny")
    assert read_text_lines(p) == ["x\r", "y"]


def test_over_one_megabyte_is_none(tmp_path):
    p = write(tmp_path, "big.txt", b"a" * 1_048_577)
    assert read_text_lines(p) is None
    q = write(tmp_path, "ok.txt", b"a" * 1_048_576)
    assert read_text_lines(q) is not None


def test_nul_in_first_8k_is_none_but_later_is_not(tmp_path):
    early = write(tmp_path, "early.bin", b"ab\x00cd")
    late = write(tmp_path, "late.txt", b"a" * 8192 + b"\x00")
    assert read_text_lines(early) is None
    assert read_text_lines(late) is not None


def test_invalid_utf8_is_none(tmp_path):
    p = write(tmp_path, "bad.txt", b"\xff\xfe abc")
    assert read_text_lines(p) is None


def make_latin1_name(root):
    bad = os.path.join(os.fsencode(root), b"caf\xe9.md")
    try:
        with open(bad, "wb") as f:
            f.write(b"menu\n")
    except OSError:
        pytest.skip("filesystem refuses non-UTF-8 file names")


def test_non_utf8_file_name_is_skipped_in_a_folder(ask_home, tmp_path):
    root = tmp_path / "r"
    write(root, "good.md", "good line\n")
    make_latin1_name(root)
    assert list_files(root) == [Path("good.md")]
    assert add_repo(connect(), root).file_count == 1


def test_non_utf8_file_name_is_skipped_in_git(ask_home, tmp_path):
    root = tmp_path / "g"
    write(root, "good.md", "good line\n")
    make_latin1_name(root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    assert list_files(root) == [Path("good.md")]
    assert add_repo(connect(), root).file_count == 1


def test_file_over_one_megabyte_is_never_read(tmp_path, monkeypatch):
    big = tmp_path / "big.txt"
    big.touch()
    os.truncate(big, 2 * 1_048_576)

    def refuse(*args, **kwargs):
        raise AssertionError("read a file over 1 MB")

    monkeypatch.setattr(Path, "read_bytes", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    monkeypatch.setattr("builtins.open", refuse)
    assert read_text_lines(big) is None


def test_surrogate_name_from_the_walk_is_dropped(tmp_path, monkeypatch):
    bad = os.fsdecode(b"caf\xe9.md")
    monkeypatch.setattr("ask.files._is_git_root", lambda root: False)
    monkeypatch.setattr("ask.files.os.walk", lambda root: [(str(root), [], ["good.md", bad])])
    monkeypatch.setattr("ask.files._wanted", lambda root, rel: True)
    assert list_files(tmp_path) == [Path("good.md")]
