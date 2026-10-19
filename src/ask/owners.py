import re
from dataclasses import dataclass, field
from pathlib import Path

CODEOWNERS_LOCATIONS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


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
    body = body.lstrip("/")
    one_level = not dir_only and body.endswith("/*")

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
        if pattern.startswith("!") or "[" in pattern or "]" in pattern:
            continue
        rules.append(Rule(pattern, tokens[1:], number, _compile(pattern)))
    return rules


def owners_for_path(rules: list[Rule], path: str) -> Rule | None:
    """Return the last rule matching a repo-relative POSIX path, or None. The winner may have no owners."""
    for rule in reversed(rules):
        regex = rule.regex or _compile(rule.pattern)
        if regex.match(path):
            return rule
    return None
