"""CODEOWNERS rules, services.json services and recent git committers."""

import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ask.files import read_text_lines
from ask.search import content_words

CODEOWNERS_LOCATIONS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
OWNER_WORDS = frozenset("own owns owner owners owned review reviewer reviewers".split())


@dataclass(frozen=True)
class Rule:
    """One CODEOWNERS line. `owners` is a list and may be empty, which clears ownership. `line` is 1-based."""

    pattern: str
    owners: list[str]
    line: int
    regex: re.Pattern | None = field(default=None, compare=False, repr=False)


def find_codeowners(root: Path) -> Path | None:
    """Return the first regular file among .github/CODEOWNERS, CODEOWNERS and docs/CODEOWNERS."""
    for rel in CODEOWNERS_LOCATIONS:
        candidate = Path(root) / rel
        if candidate.is_file():
            return candidate
    return None


def _strip_comment(line: str) -> str:
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and line[i + 1 : i + 2] == "#":
            out.append("#")
            i += 2
            continue
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _compile(pattern: str) -> re.Pattern:
    dir_only = pattern.endswith("/")
    body = pattern.rstrip("/") if dir_only else pattern
    anchored = body.startswith("/") or "/" in body
    one_level = not dir_only and (body == "/*" or body.endswith("/*"))
    body = body.lstrip("/")

    parts = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif body.startswith("/**", i) and i + 3 == len(body):
            parts.append("/.*")
            i += 3
        elif body.startswith("**", i):
            parts.append(".*")
            i += 2
        elif body[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif body[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(body[i]))
            i += 1

    prefix = "" if anchored else "(?:.*/)?"
    if dir_only:
        suffix = "/.*"
    elif one_level:
        suffix = ""
    else:
        suffix = "(?:/.*)?"
    return re.compile(f"^{prefix}{''.join(parts)}{suffix}$", re.DOTALL)


def parse_codeowners(text: str) -> list[Rule]:
    """Parse CODEOWNERS text into rules in file order, skipping negations and bracket ranges."""
    rules = []
    for number, raw in enumerate(text.split("\n"), start=1):
        if raw.endswith("\r"):
            raw = raw[:-1]
        tokens = _strip_comment(raw).split()
        if not tokens:
            continue
        pattern = tokens[0]
        if pattern.startswith("!") or "[" in pattern or "]" in pattern or not pattern.strip("/"):
            continue
        rules.append(Rule(pattern, tokens[1:], number, _compile(pattern)))
    return rules


def owners_for_path(rules: list[Rule], path: str) -> Rule | None:
    """Return the last rule matching a repo-relative POSIX path, or None. The winner may have no owners."""
    for rule in reversed(rules):
        if rule.regex.match(path):
            return rule
    return None


@dataclass(frozen=True)
class Service:
    """One services.json entry with its own keys. `owner_line` is the 1-based line inside this entry where `"owner":` holds its owner, or 0 when there is none."""

    name: str
    description: str | None
    team: str | None
    owner: str | None
    owner_slack: str | None
    repo: str | None
    doc: str | None
    slack_channel: str | None
    owner_line: int


_SERVICES_KEY = re.compile(r'"services"\s*:\s*\[')


def _entry_spans(text: str, count: int) -> list[tuple[int, int]] | None:
    """0-based (first, last) line of each element of the services array, found by decoding it in place. None when the array cannot be located."""
    found = _SERVICES_KEY.search(text)
    if found is None:
        return None
    decoder = json.JSONDecoder()
    spans = []
    pos = found.end()
    for _ in range(count):
        while pos < len(text) and text[pos] in " \t\r\n,":
            pos += 1
        try:
            _, end = decoder.raw_decode(text, pos)
        except ValueError:
            return None
        spans.append((text.count("\n", 0, pos), text.count("\n", 0, end)))
        pos = end
    return spans


def _owner_line(lines: list[str], span: tuple[int, int] | None, owner: object) -> int:
    if span is None or not isinstance(owner, str):
        return 0
    pattern = re.compile(r'"owner"\s*:\s*' + re.escape(json.dumps(owner, ensure_ascii=False)))
    return next((i + 1 for i in range(span[0], span[1] + 1) if pattern.search(lines[i])), 0)


def load_services(root: Path) -> list[Service]:
    """Read services.json at a repo root. A missing or malformed file gives an empty list."""
    lines = read_text_lines(Path(root) / "services.json")
    if lines is None:
        return []
    text = "\n".join(lines)
    try:
        data = json.loads(text)
    except ValueError:
        return []
    entries = data.get("services") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    spans = _entry_spans(text, len(entries)) or [None] * len(entries)
    out = []
    for entry, span in zip(entries, spans):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        out.append(
            Service(
                entry["name"],
                entry.get("description"),
                entry.get("team"),
                entry.get("owner"),
                entry.get("owner_slack"),
                entry.get("repo"),
                entry.get("doc"),
                entry.get("slack_channel"),
                _owner_line(lines, span, entry.get("owner")),
            )
        )
    return out


def _contains_run(words: list[str], run: list[str]) -> bool:
    size = len(run)
    return size > 0 and any(words[i : i + size] == run for i in range(len(words) - size + 1))


def resolve_service(question: str, services: list[Service]) -> list[Service]:
    """Services named in the question, matching every part of a hyphenated name in order. With no name match, a word that is a description word of exactly one service names it."""
    words = [w for w in content_words(question) if w not in OWNER_WORDS]
    named = [s for s in services if _contains_run(words, content_words(s.name))]
    if named:
        return named
    holders: dict[str, set[int]] = {}
    for index, s in enumerate(services):
        for token in content_words(s.description or ""):
            holders.setdefault(token, set()).add(index)
    picked: list[int] = []
    for word in words:
        found = holders.get(word, set())
        if len(found) == 1 and next(iter(found)) not in picked:
            picked.append(next(iter(found)))
    return [services[i] for i in picked]


_SCP_REMOTE = re.compile(r"^[^@/\s]+@([^:/\s]+):([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_URL_REMOTE = re.compile(r"^(?:ssh|https?)://(?:[^/\s]*@)?([^/:@\s]+)(?::\d+)?/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


def _git(root: Path, *args: str) -> str | None:
    """Run git in a folder that is itself a git root and return stdout. Anything else, or any git failure, gives None."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(root).resolve():
            return None
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def remote_info(root: Path) -> dict | None:
    """Host, org and repo name parsed from the origin remote of a git root, or None. The raw URL and any user or token in it are never returned."""
    url = _git(root, "remote", "get-url", "origin")
    if url is None:
        return None
    match = _SCP_REMOTE.match(url.strip()) or _URL_REMOTE.match(url.strip())
    if match is None:
        return None
    host, org, name = match.groups()
    return {"host": host, "org": org, "name": name}


def recent_committers(root: Path, path: str | list[str] | None, n: int = 3) -> list[dict]:
    """Top committers by count over the last 200 commits touching the path or paths, from git log. These are never owners. Unless the root is a git root, or on any git failure, the list is empty."""
    paths = [path] if isinstance(path, str) else list(path or [])
    cmd = ["log", "-n", "200", "--format=%an"]
    if paths:
        cmd += ["--", *paths]
    log = _git(root, *cmd)
    if log is None:
        return []
    counts = Counter(name for name in log.split("\n") if name)
    return [{"name": name, "commits": c} for name, c in counts.most_common(n)]
