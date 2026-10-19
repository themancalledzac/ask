"""Caller role storage and visibility rules. The role is read only from config.toml."""

import tomllib

from ask.home import ask_home
from ask.model import ROLES


def get_role() -> str:
    """Return the stored role, or guest when unset, unreadable or not a known role."""
    path = ask_home() / "config.toml"
    try:
        with path.open("rb") as f:
            role = tomllib.load(f).get("role")
    except (OSError, ValueError):
        return "guest"
    return role if role in ROLES else "guest"


def set_role(role: str) -> None:
    """Write the role to config.toml. Raise ValueError for a role not in ROLES."""
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}', use one of: {', '.join(ROLES)}")
    (ask_home() / "config.toml").write_text(f'role = "{role}"\n')


def can_see(caller_role: str, repo_role: str) -> bool:
    """An employee sees every repo. A guest sees only repos set to guest."""
    return caller_role == "employee" or repo_role == "guest"
