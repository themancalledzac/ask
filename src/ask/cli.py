"""Command line entry point. Only rbac is implemented so far."""

import sys

from ask.access import get_role, set_role
from ask.model import ROLES, AskError

COMMANDS = ("add-repo", "list-repos", "remove-repo", "update-repo", "rbac")
USAGE = 'usage: ask "<question>" | ask rbac [employee|guest] | ask add-repo|list-repos|remove-repo|update-repo'


def _rbac(args: list[str]) -> int:
    """Print the current role, or set it when one argument is given."""
    if not args:
        print(get_role())
        return 0
    if len(args) > 1:
        raise AskError(f"rbac takes one role, use one of: {', '.join(ROLES)}")
    try:
        set_role(args[0])
    except ValueError as e:
        raise AskError(str(e)) from e
    print(f"role set to {args[0]}")
    return 0


def _not_implemented(name: str) -> int:
    """Placeholder for commands added in later tasks."""
    print(f"{name}: not implemented yet", file=sys.stderr)
    return 3


def main(argv: list[str] | None = None) -> int:
    """Dispatch argv and return the exit code. AskError becomes a stderr line and 3."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 3
    try:
        if args[0] == "rbac":
            return _rbac(args[1:])
        if args[0] in COMMANDS:
            return _not_implemented(args[0])
        return _not_implemented("question")
    except AskError as e:
        print(str(e), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
