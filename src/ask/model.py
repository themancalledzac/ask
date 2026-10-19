"""Shared constants, the citation type and the error type."""

from dataclasses import dataclass

ROLES = ("employee", "guest")
REFUSED = "Refused: needs employee access"
NOT_FOUND = "Not found in added repos."


@dataclass
class Citation:
    repo: str
    path: str
    line: int
    quote: str


class AskError(Exception):
    """A usage or input error. The message is one line and says how to fix it."""
