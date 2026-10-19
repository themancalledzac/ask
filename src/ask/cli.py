"""Command line entry point."""

import json
import sys
from pathlib import Path

from ask.access import can_see, get_role, set_role
from ask.answer import answer
from ask.model import REFUSED, ROLES, AskError
from ask.store import add_repo, connect, list_repos, remove_repo, set_repo_role

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


def _add_repo(args: list[str]) -> int:
    """Index a folder: ask add-repo <path> [--name N]."""
    name = None
    if "--name" in args:
        i = args.index("--name")
        if i + 1 >= len(args):
            raise AskError("--name needs a value. Run: ask add-repo <path> --name <name>")
        name = args[i + 1]
        args = args[:i] + args[i + 2 :]
    if len(args) != 1:
        raise AskError("add-repo takes one folder. Run: ask add-repo <path> [--name N]")
    repo = add_repo(connect(), Path(args[0]), name)
    print(f"added {repo.name} ({repo.file_count} files, role {repo.role})")
    return 0


def _list_repos(args: list[str]) -> int:
    """Print the repos the caller may see, one per line."""
    role = get_role()
    repos = [r for r in list_repos(connect()) if can_see(role, r.role)]
    if not repos:
        print("No repos added. Run: ask add-repo <path>")
    for r in repos:
        print(f"{r.name}\t{r.role}\t{r.file_count} files\t{r.path}")
    return 0


def _remove_repo(args: list[str]) -> int:
    """Delete a repo from the index: ask remove-repo <name>."""
    if len(args) != 1:
        raise AskError("remove-repo takes one name. Run: ask remove-repo <name>")
    remove_repo(connect(), args[0])
    print(f"removed {args[0]}")
    return 0


def _update_repo(args: list[str]) -> int:
    """Change a repo's role: ask update-repo <name> <employee|guest>."""
    if len(args) != 2:
        raise AskError("update-repo takes a name and a role. Run: ask update-repo <name> <employee|guest>")
    set_repo_role(connect(), args[0], args[1])
    print(f"updated {args[0]} to role {args[1]}")
    return 0


REPO_COMMANDS = {
    "add-repo": (_add_repo, True),
    "list-repos": (_list_repos, False),
    "remove-repo": (_remove_repo, True),
    "update-repo": (_update_repo, True),
}


EXIT_CODES = {"answered": 0, "not_found": 1, "refused": 2}


def _parse_question(args: list[str]) -> tuple[str, bool, str | None]:
    """Split argv into the question words, the --json switch and the --repo value."""
    words, as_json, repo = [], False, None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            as_json = True
        elif arg == "--repo":
            if i + 1 >= len(args):
                raise AskError('--repo needs a value. Run: ask "<question>" --repo <name>')
            repo = args[i + 1]
            i += 1
        elif arg.startswith("--"):
            raise AskError(f"Unknown option {arg}. {USAGE}")
        else:
            words.append(arg)
        i += 1
    return " ".join(words), as_json, repo


def _ask(args: list[str]) -> int:
    """Answer a question as the stored role and print text or JSON."""
    question, as_json, repo = _parse_question(args)
    result = answer(connect(), question, get_role(), repo)
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["message"])
        for h in result["hits"]:
            print(f"{h['repo']}:{h['path']}:{h['line']}  {h['quote']}")
    return EXIT_CODES[result["status"]]


def main(argv: list[str] | None = None) -> int:
    """Dispatch argv and return the exit code. AskError becomes a stderr line and 3."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 3
    try:
        if args[0] == "rbac":
            return _rbac(args[1:])
        if args[0] in REPO_COMMANDS:
            handler, needs_employee = REPO_COMMANDS[args[0]]
            if needs_employee and get_role() != "employee":
                print(REFUSED)
                return 2
            return handler(args[1:])
        return _ask(args)
    except AskError as e:
        print(str(e), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
