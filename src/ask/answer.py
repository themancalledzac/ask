"""Route a question to the right lookup and build the JSON result."""

import sqlite3
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ask.access import can_see
from ask.files import read_text_lines
from ask.model import NOT_FOUND, REFUSED, Citation
from ask.owners import (
    OWNER_WORDS,
    find_codeowners,
    load_services,
    owners_for_path,
    parse_codeowners,
    recent_committers,
    resolve_service,
)
from ask.redact import redact_lines
from ask.search import content_words, fts_search
from ask.store import Repo, list_repos

MAX_PATH_MATCHES = 5
TRAILING_PUNCTUATION = "?.,:;!"


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


def _quote(root: Path, rel: str, line: int) -> str | None:
    lines = read_text_lines(root / rel)
    if lines is None or not 0 < line <= len(lines):
        return None
    return redact_lines(lines)[line - 1].strip()


def _owner(name: str, team: str | None, repo: Repo, rel: str, line: int) -> dict | None:
    quote = _quote(Path(repo.path), rel, line)
    if quote is None:
        return None
    return {"name": name, "team": team, "citation": asdict(Citation(repo.name, rel, line, quote))}


def _split_paths(question: str) -> tuple[str, list[str]]:
    """Split the question into its words outside path tokens and the path tokens themselves."""
    rest, paths = [], []
    for raw in question.split():
        token = raw.rstrip(TRAILING_PUNCTUATION)
        if token.startswith("./"):
            token = token[2:]
        token = token.lstrip("/")
        if token and ("/" in token or "." in token):
            if token not in paths:
                paths.append(token)
        else:
            rest.append(raw)
    return " ".join(rest), paths


def _match_paths(con: sqlite3.Connection, repo: Repo, tokens: list[str]) -> list[tuple[str, str]]:
    """Pairs of (label, path to look up) for tokens that name an indexed file or directory in the repo."""
    rows = con.execute("SELECT DISTINCT path FROM chunks WHERE repo = ?", (repo.name,))
    paths = [r[0] for r in rows]
    out = []
    for token in tokens:
        prefix = token.rstrip("/") + "/"
        if token in paths:
            out.append((token, token))
        elif any(p.startswith(prefix) for p in paths):
            out.append((token, prefix))
    return out


def _service_owners(question: str, visible: list[Repo]) -> tuple[list[str], list[dict]]:
    pairs = [(repo, s) for repo in visible for s in load_services(Path(repo.path))]
    home = {id(s): repo for repo, s in pairs}
    labels, owners = [], []
    for s in resolve_service(question, [s for _, s in pairs]):
        if not s.owner or not s.owner_line:
            continue
        entry = _owner(s.owner, s.team, home[id(s)], "services.json", s.owner_line)
        if entry is not None and s.owner in entry["citation"]["quote"]:
            owners.append(entry)
            if s.name not in labels:
                labels.append(s.name)
    return labels, owners


def _path_owners(con: sqlite3.Connection, tokens: list[str], visible: list[Repo]) -> tuple[list[str], list[dict], Counter]:
    labels, owners, committers, seen = [], [], Counter(), 0
    if not tokens:
        return labels, owners, committers
    for repo in visible:
        root = Path(repo.path)
        codeowners = find_codeowners(root)
        if codeowners is None:
            continue
        lines = read_text_lines(codeowners)
        if lines is None:
            continue
        rules = parse_codeowners("\n".join(lines))
        rel = codeowners.relative_to(root).as_posix()
        for label, path in _match_paths(con, repo, tokens):
            if seen == MAX_PATH_MATCHES:
                return labels, owners, committers
            seen += 1
            rule = owners_for_path(rules, path)
            if rule is None or not rule.owners:
                continue
            found = [e for e in (_owner(o, None, repo, rel, rule.line) for o in rule.owners) if e]
            if not found:
                continue
            owners.extend(found)
            if label not in labels:
                labels.append(label)
            for c in recent_committers(root, path):
                committers[c["name"]] += c["commits"]
    return labels, owners, committers


def _owners(con: sqlite3.Connection, question: str, visible: list[Repo]) -> dict:
    """Owners from services.json and CODEOWNERS in visible repos only. Path tokens are matched against CODEOWNERS and never against service names. Never falls back to text search."""
    rest, tokens = _split_paths(question)
    service_labels, service_owners = _service_owners(rest, visible)
    path_labels, path_owners, committers = _path_owners(con, tokens, visible)
    owners = service_owners + path_owners
    if not owners:
        return _result("not_found", None, NOT_FOUND)
    result = _result("answered", "owner", f"Owner of {', '.join(service_labels + path_labels)}:")
    result["owners"] = owners
    result["recent_committers"] = [{"name": n, "commits": c} for n, c in committers.most_common(3)]
    return result


def is_owner_question(question: str) -> bool:
    """True when the question's content words include an ownership or review word."""
    return any(w in OWNER_WORDS for w in content_words(question))


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
    if is_owner_question(question):
        return _owners(con, question, visible)
    return _search(con, question, visible)
