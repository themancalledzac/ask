"""Secret redaction applied to every line before it reaches the index."""

import re

MASK = "[redacted]"

_PEM_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_PEM_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")
_AWS = re.compile(r"AKIA[0-9A-Z]{16}")
_PREFIXED = re.compile(
    r"(?<![A-Za-z0-9_-])(?:ghp_|gho_|github_pat_|sk-|xox[abpr]-)[A-Za-z0-9_-]{16,}"
)
_URL_PASSWORD = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_ASSIGNMENT = re.compile(
    r"""(?i)((?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['"]?)[^\s'"]{8,}"""
)


def redact(line: str) -> str:
    """Replace API keys, URL passwords, JWTs and assigned secret values in one line."""
    line = _AWS.sub(MASK, line)
    line = _PREFIXED.sub(MASK, line)
    line = _URL_PASSWORD.sub(rf"\1{MASK}@", line)
    line = _JWT.sub(MASK, line)
    return _ASSIGNMENT.sub(rf"\1{MASK}", line)


def redact_lines(lines: list[str]) -> list[str]:
    """Redact a whole file. PEM private key blocks become one mask per line, so the count never changes."""
    out = []
    in_pem = False
    for line in lines:
        if in_pem:
            out.append(MASK)
            in_pem = not _PEM_END.search(line)
        elif _PEM_BEGIN.search(line):
            out.append(MASK)
            in_pem = not _PEM_END.search(line)
        else:
            out.append(redact(line))
    return out
