"""SQLite repo registry and FTS5 chunk index stored in $ASK_HOME/index.db."""

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from ask.files import list_files, read_text_lines
from ask.home import ask_home
from ask.model import ROLES, AskError
from ask.redact import redact_lines

MAX_CHUNK_LINES = 20
SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos(
    name TEXT PRIMARY KEY,
    path TEXT,
    role TEXT DEFAULT 'employee',
    file_count INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    text, repo UNINDEXED, path UNINDEXED, start_line UNINDEXED,
    tokenize='unicode61'
);
"""


@dataclass
class Repo:
    name: str
    path: str
    role: str
    file_count: int


def connect() -> sqlite3.Connection:
    """Open $ASK_HOME/index.db and create the schema if it is missing. An index from an older schema version is rebuilt from each repo's folder."""
    con = sqlite3.connect(ask_home() / "index.db")
    if con.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        _rebuild(con)
    return con


def _rebuild(con: sqlite3.Connection) -> None:
    """Recreate the chunk table and re-index every registered repo, keeping its name and role. A repo whose folder cannot be read stays registered with no chunks, and one line goes to stderr."""
    with con:
        con.execute("DROP TABLE IF EXISTS chunks")
        con.executescript(SCHEMA)
    for name, path in con.execute("SELECT name, path FROM repos ORDER BY name").fetchall():
        try:
            add_repo(con, Path(path), name)
        except AskError as e:
            with con:
                con.execute("UPDATE repos SET file_count = 0 WHERE name = ?", (name,))
            print(f"Could not re-index {name}: {e}", file=sys.stderr)
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _chunks(lines: list[str]) -> list[tuple[int, str]]:
    """Split lines into runs of non-blank lines, at most 20 each. Returns (1-based start line, text)."""
    out = []
    run: list[str] = []
    start = 0

    def flush() -> None:
        if run:
            out.append((start, "\n".join(run)))
            run.clear()

    for number, line in enumerate(lines, 1):
        if line.strip() == "":
            flush()
            continue
        if not run:
            start = number
        run.append(line)
        if len(run) == MAX_CHUNK_LINES:
            flush()
    flush()
    return out


def _check_folder(path: Path, given: Path) -> None:
    if not path.exists():
        raise AskError(f"No such folder: {given}. Pass a folder path.")
    if not path.is_dir():
        raise AskError(f"Not a folder: {given}. Pass a folder, not a file.")
    if not os.access(path, os.R_OK | os.X_OK):
        raise AskError(f"Cannot read {given}: permission denied. Fix the folder's permissions.")


def add_repo(con: sqlite3.Connection, path: Path, name: str | None = None) -> Repo:
    """Index a folder under its basename or the given name. Re-adding the same path replaces its chunks and keeps its role."""
    resolved = path.resolve()
    _check_folder(resolved, path)
    name = name or resolved.name
    row = con.execute("SELECT path, role FROM repos WHERE name = ?", (name,)).fetchone()
    if row and row[0] != str(resolved):
        raise AskError(f"Repo name {name} is already used for {row[0]}. Pass --name to pick another.")
    role = row[1] if row else "employee"
    try:
        rels = list_files(resolved)
    except OSError as e:
        raise AskError(f"Cannot read {path}: {e.strerror or 'read failed'}. Fix the folder's permissions.") from e
    rows = []
    file_count = 0
    for rel in rels:
        lines = read_text_lines(resolved / rel)
        if lines is None:
            continue
        file_count += 1
        for start, text in _chunks(redact_lines(lines)):
            rows.append((text, name, rel.as_posix(), start))
    with con:
        con.execute("DELETE FROM chunks WHERE repo = ?", (name,))
        con.execute(
            "INSERT OR REPLACE INTO repos(name, path, role, file_count) VALUES (?, ?, ?, ?)",
            (name, str(resolved), role, file_count),
        )
        con.executemany(
            "INSERT INTO chunks(text, repo, path, start_line) VALUES (?, ?, ?, ?)", rows
        )
    return Repo(name, str(resolved), role, file_count)


def _require(con: sqlite3.Connection, name: str) -> None:
    if not con.execute("SELECT 1 FROM repos WHERE name = ?", (name,)).fetchone():
        raise AskError(f"No repo named {name}. Run: ask list-repos")


def remove_repo(con: sqlite3.Connection, name: str) -> None:
    """Delete a repo and all its chunks. Raise AskError for an unknown name."""
    _require(con, name)
    with con:
        con.execute("DELETE FROM chunks WHERE repo = ?", (name,))
        con.execute("DELETE FROM repos WHERE name = ?", (name,))


def set_repo_role(con: sqlite3.Connection, name: str, role: str) -> None:
    """Set a repo's role. Raise AskError for an unknown repo or a role not in ROLES."""
    if role not in ROLES:
        raise AskError(f"Unknown role {role}. Use one of: {', '.join(ROLES)}")
    _require(con, name)
    with con:
        con.execute("UPDATE repos SET role = ? WHERE name = ?", (role, name))


def list_repos(con: sqlite3.Connection) -> list[Repo]:
    """Return every repo ordered by name."""
    rows = con.execute("SELECT name, path, role, file_count FROM repos ORDER BY name")
    return [Repo(*r) for r in rows]
