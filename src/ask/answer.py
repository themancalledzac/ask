"""Route a question to the right lookup and build the JSON result."""

import sqlite3
from dataclasses import asdict
from pathlib import Path

from ask.access import can_see
from ask.model import NOT_FOUND, REFUSED, Citation
from ask.search import content_words, fts_search
from ask.store import Repo, list_repos


def _result(status: str, kind: str | None, message: str, hits: list[Citation] | None = None) -> dict:
    return {
        "status": status,
        "kind": kind,
        "message": message,
        "owners": [],
        "hits": [asdict(h) for h in hits or []],
        "recent_committers": [],
    }


def _resolve_repo(repos: list[Repo], ref: str) -> Repo | None:
    """Match a repo by name, or an absolute path to a repo folder or anything inside it. The deepest repo wins."""
    for r in repos:
        if r.name == ref:
            return r
    if not Path(ref).is_absolute():
        return None
    target = Path(ref).resolve()
    inside = [r for r in repos if target == Path(r.path) or Path(r.path) in target.parents]
    return max(inside, key=lambda r: len(r.path), default=None)


def _search(con: sqlite3.Connection, question: str, visible: list[Repo]) -> dict:
    hits = fts_search(con, content_words(question), [r.name for r in visible], question=question)
    if not hits:
        return _result("not_found", None, NOT_FOUND)
    return _result("answered", "search", "Found in:", hits)


def answer(con: sqlite3.Connection, question: str, role: str, repo: str | None = None) -> dict:
    """Answer a question for a caller with the given role. A named repo the role cannot see is refused; an unknown one is not found."""
    repos = list_repos(con)
    if repo is not None:
        target = _resolve_repo(repos, repo)
        if target is None:
            return _result("not_found", None, NOT_FOUND)
        if not can_see(role, target.role):
            return _result("refused", None, REFUSED)
        repos = [target]
    visible = [r for r in repos if can_see(role, r.role)]
    return _search(con, question, visible)
