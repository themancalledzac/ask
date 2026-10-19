"""Full-text search over the chunk index and choice of the cited line."""

import math
import re
import sqlite3

from ask.model import Citation

STOPWORDS = frozenset(
    "a an and are as at be can do does for from get have how i in is it me my of on or our "
    "should so the there this to was what when where which who whose why will with you your "
    "now just s".split()
)

_TOKEN = re.compile(r"[^\W_]+")
PREFIX_MIN = 4
STEM = 5
RATIO = 0.6
CANDIDATES = 200
ECHO_MIN_WORDS = 3


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def content_words(q: str) -> list[str]:
    """Lowercase words split on anything that is not a letter or digit, without stopwords, in order, deduplicated."""
    seen: dict[str, None] = {}
    for token in _tokens(q):
        if token not in STOPWORDS:
            seen.setdefault(token)
    return list(seen)


def _term(word: str) -> str:
    quoted = '"' + word.replace('"', '""') + '"'
    return quoted + "*" if len(word) >= PREFIX_MIN else quoted


def _covers(word: str, token: str) -> bool:
    if token == word:
        return True
    if len(word) >= PREFIX_MIN and token.startswith(word):
        return True
    return len(word) >= STEM and len(token) >= STEM and word[:STEM] == token[:STEM]


def _score(words: list[str], tokens: list[str]) -> int:
    return sum(any(_covers(w, t) for t in tokens) for w in words)


def _need(count: int) -> int:
    return count if count <= 2 else math.ceil(RATIO * count)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _echoes(text: str, echo: str) -> bool:
    return bool(echo) and any(echo in _normalize(line) for line in text.split("\n"))


def _best_line(text: str, words: list[str]) -> tuple[int, str] | None:
    """Index and trimmed text of the line covering the most words; the first line wins ties. None when no line covers any."""
    best, best_score = None, 0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        score = _score(words, _tokens(line))
        if score > best_score:
            best, best_score = i, score
    return None if best is None else (best, lines[best].strip())


def fts_search(
    con: sqlite3.Connection,
    words: list[str],
    repos: list[str],
    limit: int = 3,
    question: str | None = None,
) -> list[Citation]:
    """Return up to limit citations from the named repos. A chunk needs 60% of the words (all, up to two), ranked by words covered then BM25. A chunk that quotes a question of 3 or more words is a chat log and is dropped."""
    if not words or not repos:
        return []
    marks = ", ".join("?" for _ in repos)
    sql = (
        "SELECT text, repo, path, start_line FROM chunks "
        f"WHERE chunks MATCH ? AND repo IN ({marks}) ORDER BY bm25(chunks) LIMIT {CANDIDATES}"
    )
    match = " OR ".join(_term(w) for w in words)
    rows = con.execute(sql, (match, *repos)).fetchall()
    need = _need(len(words))
    echo = _normalize(question).rstrip("?!. \t\n") if question else ""
    if len(echo.split()) < ECHO_MIN_WORDS:
        echo = ""
    kept = []
    for rank, (text, repo, path, start) in enumerate(rows):
        covered = _score(words, _tokens(text))
        if covered >= need and not _echoes(text, echo):
            kept.append((-covered, rank, text, repo, path, start))
    kept.sort(key=lambda k: k[:2])
    cites = []
    for _, _, text, repo, path, start in kept:
        found = _best_line(text, words)
        if found is None:
            continue
        offset, quote = found
        cites.append(Citation(repo, path, int(start) + offset, quote))
        if len(cites) == limit:
            break
    return cites
