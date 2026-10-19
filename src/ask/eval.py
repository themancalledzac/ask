"""Score the tool against JSONL rows: python -m ask.eval eval/<rows>.jsonl [--detail] [--repos PATH]."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ask.answer import answer
from ask.model import AskError
from ask.store import add_repo, connect, set_repo_role

PIN_FAILED = 3


def _check(row: dict, result: dict) -> str | None:
    """Return why the result fails the row, or None when it passes."""
    if result["status"] != row["status"]:
        return f"status {result['status']}, expected {row['status']}"
    owner_names = [o["name"] for o in result["owners"]]
    for wanted in row.get("owners_include", []):
        if not any(wanted in name for name in owner_names):
            return f"owner {wanted} missing"
    suffix = row.get("path_endswith")
    if suffix:
        paths = [h["path"] for h in result["hits"]]
        paths += [o["citation"]["path"] for o in result["owners"] if o.get("citation")]
        if not any(p.endswith(suffix) for p in paths):
            return f"no citation path ends with {suffix}"
    text = json.dumps(result).lower()
    for banned in row.get("must_not_contain", []):
        if banned.lower() in text:
            return f"result contains {banned}"
    return None


def _head(path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    )
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def _pin_error(entries: list[dict], root: Path) -> str | None:
    """Return the stderr line for the first heldout repo not at its pin, or None."""
    for entry in entries:
        pin = entry.get("pin")
        if not pin:
            continue
        sha = _head(root / entry["path"])
        if sha[: len(pin)] != pin:
            return f"held-out repo {entry['name']} is at {sha}, expected {pin}"
    return None


def _load(entries: list[dict], root: Path) -> None:
    con = connect()
    try:
        for entry in entries:
            path = root / entry["path"]
            if not path.exists():
                print(f"skipping repo {entry['name']}: {path} does not exist", file=sys.stderr)
                continue
            try:
                add_repo(con, path, name=entry["name"])
            except AskError as e:
                print(f"skipping repo {entry['name']}: {e}", file=sys.stderr)
                continue
            set_repo_role(con, entry["name"], entry["role"])
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ask.eval")
    parser.add_argument("rows")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--repos")
    args = parser.parse_args(argv)

    rows_path = Path(args.rows)
    repos_path = Path(args.repos) if args.repos else rows_path.resolve().parent / "repos.json"
    root = repos_path.resolve().parent.parent
    config = json.loads(repos_path.read_text())
    heldout = rows_path.name.startswith("heldout")
    entries = config["heldout" if heldout else "seen"]

    if heldout:
        error = _pin_error(entries, root)
        if error:
            print(error, file=sys.stderr)
            return PIN_FAILED

    rows = [json.loads(line) for line in rows_path.read_text().splitlines() if line.strip()]
    previous = os.environ.get("ASK_HOME")
    os.environ["ASK_HOME"] = tempfile.mkdtemp()
    try:
        _load(entries, root)
        con = connect()
        try:
            failures = []
            for row in rows:
                result = answer(con, row["q"], role=row["role"], repo=row.get("repo"))
                reason = _check(row, result)
                if reason:
                    failures.append((row["q"], reason))
        finally:
            con.close()
    finally:
        if previous is None:
            os.environ.pop("ASK_HOME", None)
        else:
            os.environ["ASK_HOME"] = previous

    if args.detail:
        for q, reason in failures:
            print(f"FAIL {q}: {reason}")
    print(f"{len(rows) - len(failures)}/{len(rows)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
