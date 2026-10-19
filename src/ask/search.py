"""Full-text search over the chunk index and choice of the cited line."""

import re
import sqlite3

from ask.model import Citation

STOPWORDS = frozenset(
    "a an and are as at be can do does for from get have how i in is it me my of on or our "
    "should so the there this to was what when where which who whose why will with you your "
    "now just s".split()
)

_TOKEN = re.compile(r"[^\W_]+")
PREFIX = 5


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def content_words(q: str) -> list[str]:
    """Lowercase words split on anything that is not a letter or digit, without stopwords, in order, deduplicated."""
    seen: dict[str, None] = {}
    for token in _tokens(q):
        if token not in STOPWORDS:
            seen.setdefault(token)
    return list(seen)


def _and_group(words: list[str]) -> str:
    return " AND ".join(f'"{w}"' for w in words)


def _match_expressions(words: list[str]) -> list[str]:
    """The strict AND query, then for 3 or more words one OR of the groups that each omit one word."""
    exprs = [_and_group(words)]
    if len(words) >= 3:
        groups = [f"({_and_group(words[:i] + words[i + 1:])})" for i in range(len(words))]
        exprs.append(" OR ".join(groups))
    return exprs


def _same_word(word: str, token: str) -> bool:
    if len(word) < PREFIX or len(token) < PREFIX:
        return word == token
    return word[:PREFIX] == token[:PREFIX]


def _best_line(text: str, words: list[str]) -> tuple[int, str]:
    """Index and trimmed text of the line holding the most content words; the first line wins ties."""
    best, best_score = 0, -1
    lines = text.split("\n")
    for i, line in enumerate(lines):
        tokens = _tokens(line)
        score = sum(any(_same_word(w, t) for t in tokens) for w in words)
        if score > best_score:
            best, best_score = i, score
    return best, lines[best].strip()


def fts_search(
    con: sqlite3.Connection, words: list[str], repos: list[str], limit: int = 3
) -> list[Citation]:
    """Return up to limit citations from the named repos, best BM25 first. Search only runs on the repos passed in."""
    if not words or not repos:
        return []
    marks = ", ".join("?" for _ in repos)
    sql = (
        "SELECT text, repo, path, start_line FROM chunks "
        f"WHERE chunks MATCH ? AND repo IN ({marks}) ORDER BY bm25(chunks) LIMIT ?"
    )
    for expr in _match_expressions(words):
        rows = con.execute(sql, (expr, *repos, limit)).fetchall()
        if rows:
            break
    else:
        return []
    cites = []
    for text, repo, path, start in rows:
        offset, quote = _best_line(text, words)
        cites.append(Citation(repo, path, int(start) + offset, quote))
    return cites
