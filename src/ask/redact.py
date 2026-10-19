"""Secret redaction applied to every line before it reaches the index."""

import re

MASK = "[redacted]"

_PEM_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_PEM_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")
_AWS = re.compile(r"AKIA[0-9A-Z]{16}")
_PREFIXED = re.compile(
    r"(?<![A-Za-z0-9_-])(?:ghp_|gho_|github_pat_|sk-|sk_live_|sk_test_|rk_live_|xox[abpr]-)[A-Za-z0-9_-]{16,}"
)
_URL_PASSWORD = re.compile(r"(?<![A-Za-z0-9+.-])([A-Za-z][A-Za-z0-9+.-]*://)[^\s/:@]+:\S*@(?=[^\s@/?#]*(?:[/?#\s]|$))")
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_BEARER = re.compile(r"""(?i)(\bBearer\s+)[^\s'"]{16,}""")
_ASSIGNMENT = re.compile(r"""(?<![\w-])([\w-]+)(["']?\s*[:=]\s*['"]?)([^\s'"]{8,})""")
_SECRET_NAME = re.compile(r"(?i)api[_-]?key|secret|token|password|passwd|_key$")


def _mask_assignment(m: re.Match) -> str:
    if not _SECRET_NAME.search(m.group(1)):
        return m.group(0)
    return m.group(1) + m.group(2) + MASK


def redact(line: str) -> str:
    """Replace API keys, URL passwords, JWTs, bearer tokens and values assigned to secret-named keys in one line."""
    line = _AWS.sub(MASK, line)
    line = _PREFIXED.sub(MASK, line)
    line = _URL_PASSWORD.sub(rf"\1{MASK}@", line)
    line = _JWT.sub(MASK, line)
    line = _BEARER.sub(rf"\1{MASK}", line)
    return _ASSIGNMENT.sub(_mask_assignment, line)


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
