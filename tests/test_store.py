import os
import sqlite3
from pathlib import Path

import pytest

from ask.answer import answer
from ask.cli import main
from ask.model import AskError
from ask.store import SCHEMA_VERSION, add_repo, connect, list_repos, remove_repo, set_repo_role

SECRET = "AKIAABCDEFGHIJKLMNOP"


def make_repo(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text)
    return root


@pytest.fixture
def repo(tmp_path):
    return make_repo(
        tmp_path / "shop",
        {"a.md": "one\ntwo\n\nthree\n", "b.txt": f"key = {SECRET}\n"},
    )


def chunk_count(con, name=None):
    if name is None:
        return con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    return con.execute("SELECT count(*) FROM chunks WHERE repo = ?", (name,)).fetchone()[0]


def test_add_then_list_shows_name_role_and_count(ask_home, repo, capsys):
    assert main(["rbac", "employee"]) == 0
    assert main(["add-repo", str(repo)]) == 0
    assert "added shop (2 files, role employee)" in capsys.readouterr().out
    assert main(["list-repos"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].split("\t")[:3] == ["shop", "employee", "2 files"]


def test_default_name_is_basename_for_dot_and_trailing_slash(ask_home, repo, monkeypatch):
    con = connect()
    assert add_repo(con, repo).name == "shop"
    monkeypatch.chdir(repo)
    assert add_repo(con, Path(".")).name == "shop"
    assert add_repo(con, Path(str(repo) + "/")).name == "shop"
    assert len(list_repos(con)) == 1


def test_readd_replaces_chunks_and_keeps_role(ask_home, repo):
    con = connect()
    add_repo(con, repo)
    set_repo_role(con, "shop", "guest")
    first = chunk_count(con)
    again = add_repo(con, repo)
    assert chunk_count(con) == first
    assert again.role == "guest"
    assert len(list_repos(con)) == 1


def test_readd_picks_up_changed_files(ask_home, repo):
    con = connect()
    add_repo(con, repo)
    (repo / "a.md").write_text("only\n")
    add_repo(con, repo)
    texts = [r[0] for r in con.execute("SELECT text FROM chunks WHERE path = 'a.md'")]
    assert texts == ["only"]


def test_chunks_split_at_blank_lines_and_cap_at_20(ask_home, tmp_path):
    body = "\n".join(f"l{i}" for i in range(45)) + "\n\nlast\n"
    root = make_repo(tmp_path / "c", {"f.txt": body})
    con = connect()
    add_repo(con, root)
    rows = con.execute(
        "SELECT start_line, text FROM chunks ORDER BY CAST(start_line AS INTEGER)"
    ).fetchall()
    assert [int(r[0]) for r in rows] == [1, 21, 41, 47]
    assert rows[0][1].count("\n") == 19
    assert rows[3][1] == "last"


def test_update_repo_changes_role(ask_home, repo, capsys):
    main(["rbac", "employee"])
    main(["add-repo", str(repo)])
    assert main(["update-repo", "shop", "guest"]) == 0
    assert list_repos(connect())[0].role == "guest"


def test_remove_deletes_chunks(ask_home, repo):
    con = connect()
    add_repo(con, repo)
    remove_repo(con, "shop")
    assert chunk_count(con) == 0
    assert list_repos(con) == []


def test_guest_refused_on_add_remove_update(ask_home, repo, capsys):
    con = connect()
    add_repo(con, repo)
    con.close()
    for argv in (
        ["add-repo", str(repo)],
        ["remove-repo", "shop"],
        ["update-repo", "shop", "guest"],
    ):
        assert main(argv) == 2
        captured = capsys.readouterr()
        assert captured.out == "Refused: needs employee access\n"
    assert len(list_repos(connect())) == 1


def test_guest_list_hides_employee_repos(ask_home, repo, tmp_path, capsys):
    other = make_repo(tmp_path / "open", {"x.txt": "hi\n"})
    con = connect()
    add_repo(con, repo)
    add_repo(con, other)
    set_repo_role(con, "open", "guest")
    con.close()
    assert main(["list-repos"]) == 0
    out = capsys.readouterr().out
    assert "open" in out
    assert "shop" not in out


def test_list_empty_message(ask_home, capsys):
    assert main(["list-repos"]) == 0
    assert capsys.readouterr().out == "No repos added. Run: ask add-repo <path>\n"


def run_error(argv, capsys):
    capsys.readouterr()
    code = main(argv)
    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert len(captured.err.strip().splitlines()) == 1
    return captured.err


def test_missing_path_error(ask_home, tmp_path, capsys):
    main(["rbac", "employee"])
    err = run_error(["add-repo", str(tmp_path / "nope")], capsys)
    assert "No such folder" in err


def test_file_path_error(ask_home, repo, capsys):
    main(["rbac", "employee"])
    err = run_error(["add-repo", str(repo / "a.md")], capsys)
    assert "Not a folder" in err


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode 000")
def test_unreadable_folder_error(ask_home, tmp_path, capsys):
    main(["rbac", "employee"])
    locked = make_repo(tmp_path / "locked", {"a.txt": "x\n"})
    locked.chmod(0)
    try:
        err = run_error(["add-repo", str(locked)], capsys)
    finally:
        locked.chmod(0o755)
    assert "permission denied" in err


def test_unknown_repo_name_errors(ask_home, capsys):
    main(["rbac", "employee"])
    assert "No repo named ghost" in run_error(["remove-repo", "ghost"], capsys)
    assert "No repo named ghost" in run_error(["update-repo", "ghost", "guest"], capsys)


def test_same_basename_different_path_needs_name(ask_home, repo, tmp_path, capsys):
    main(["rbac", "employee"])
    main(["add-repo", str(repo)])
    capsys.readouterr()
    second = make_repo(tmp_path / "deeper" / "shop", {"z.txt": "z\n"})
    err = run_error(["add-repo", str(second)], capsys)
    assert "--name" in err
    assert main(["add-repo", str(second), "--name", "shop2"]) == 0


def test_secret_never_in_chunks(ask_home, repo):
    con = connect()
    add_repo(con, repo)
    assert SECRET not in "".join(r[0] for r in con.execute("SELECT text FROM chunks"))
    assert con.execute("SELECT count(*) FROM chunks WHERE text LIKE '%redacted%'").fetchone()[0] == 1


def test_pem_block_redacted_in_index(ask_home, tmp_path):
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEabcdef\n-----END RSA PRIVATE KEY-----\n"
    root = make_repo(tmp_path / "k", {"id.txt": pem})
    con = connect()
    add_repo(con, root)
    assert "MIIEabcdef" not in "".join(r[0] for r in con.execute("SELECT text FROM chunks"))


def test_binary_and_env_files_skipped(ask_home, tmp_path):
    root = make_repo(tmp_path / "m", {"a.txt": "hi\n", ".env": "TOKEN=abcdefghijkl\n"})
    (root / "bin.dat").write_bytes(b"\0\1\2")
    con = connect()
    assert add_repo(con, root).file_count == 1


def test_default_role_is_employee(ask_home, repo):
    assert add_repo(connect(), repo).role == "employee"


def test_set_role_rejects_unknown(ask_home, repo):
    con = connect()
    add_repo(con, repo)
    with pytest.raises(AskError):
        set_repo_role(con, "shop", "boss")


def test_schema_is_fts5_unicode61_without_porter(ask_home):
    con = connect()
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'chunks'").fetchone()[0]
    assert "unicode61" in sql
    assert "porter" not in sql
    assert con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


OLD_SCHEMA = """
CREATE TABLE repos(name TEXT PRIMARY KEY, path TEXT, role TEXT DEFAULT 'employee', file_count INTEGER);
CREATE VIRTUAL TABLE chunks USING fts5(
    text, repo UNINDEXED, path UNINDEXED, start_line UNINDEXED, tokenize='porter unicode61'
);
"""


def test_old_index_is_rebuilt_keeping_names_and_roles(ask_home, tmp_path, capsys):
    kept = make_repo(tmp_path / "kept-folder", {"a.md": "the deployment guide lives here\n"})
    ask_home.mkdir()
    old = sqlite3.connect(ask_home / "index.db")
    old.executescript(OLD_SCHEMA)
    old.executemany(
        "INSERT INTO repos VALUES (?, ?, ?, ?)",
        [("kept", str(kept.resolve()), "guest", 9), ("lost", str(tmp_path / "gone"), "employee", 4)],
    )
    old.execute("INSERT INTO chunks VALUES ('stale text', 'kept', 'old.md', 1)")
    old.commit()
    old.close()
    con = connect()
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'chunks'").fetchone()[0]
    assert "porter" not in sql
    assert [(r.name, r.role, r.file_count) for r in list_repos(con)] == [("kept", "guest", 1), ("lost", "employee", 0)]
    assert con.execute("SELECT repo, path, text FROM chunks").fetchall() == [
        ("kept", "a.md", "the deployment guide lives here")
    ]
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1
    assert "lost" in err
    assert answer(con, "deploy", "guest")["status"] == "answered"
    con.close()
    connect()
    assert capsys.readouterr().err == ""
